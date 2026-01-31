"""
WhatsApp Bot Service using Baileys library (via Node.js subprocess)
This service manages WhatsApp connection, QR code generation, and message handling.
"""

import os
import json
import asyncio
import subprocess
import base64
from typing import Optional, Dict, Any
from datetime import datetime
import tempfile

class WhatsAppService:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.status = "disconnected"
        self.qr_code: Optional[str] = None
        self.phone_number: Optional[str] = None
        self.messages_count = 0
        self.last_message_at: Optional[str] = None
        self.node_script_path: Optional[str] = None
        self.error: Optional[str] = None
        self.logged_out = False
        self._setup_node_script()

    def _setup_node_script(self):
        """Create the Node.js script that uses Baileys"""
        script_content = """
const { default: makeWASocket, DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion, downloadMediaMessage } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const qrcode = require('qrcode');
const fs = require('fs');
const path = require('path');
const P = require('pino');
const http = require('http');

const AUTH_DIR = process.env.WHATSAPP_AUTH_DIR || path.join(__dirname, 'whatsapp_auth');

// Ensure auth directory exists (persistent if WHATSAPP_AUTH_DIR points to /app/storage)
try {
    if (!fs.existsSync(AUTH_DIR)) {
        fs.mkdirSync(AUTH_DIR, { recursive: true });
    }
} catch (e) {
    console.error('Failed to ensure AUTH_DIR:', e);
}
const INTERNAL_KEY = process.env.WHATSAPP_INTERNAL_KEY || '';
const INTERNAL_PORT = process.env.WHATSAPP_INTERNAL_PORT || '8791';
let currentSock = null;
let sendServerStarted = false;

function startSendServer() {
    if (sendServerStarted) return;
    sendServerStarted = true;

    const server = http.createServer(async (req, res) => {
        if (req.method !== 'POST' || req.url !== '/send') {
            res.statusCode = 404;
            return res.end('Not found');
        }

        if (INTERNAL_KEY && req.headers['x-uask-internal-key'] !== INTERNAL_KEY) {
            res.statusCode = 401;
            return res.end('Unauthorized');
        }

        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const payload = JSON.parse(body || '{}');
                const to = payload.to;
                const text = payload.text;
                if (!to || !text || !currentSock) {
                    res.statusCode = 400;
                    return res.end('Bad request');
                }
                await currentSock.sendMessage(to, { text });
                res.statusCode = 200;
                return res.end('OK');
            } catch (err) {
                res.statusCode = 500;
                return res.end('Error');
            }
        });
    });

    server.listen(parseInt(INTERNAL_PORT, 10), '0.0.0.0', () => {
        console.log(JSON.stringify({ type: 'status', status: 'send_server_ready', port: INTERNAL_PORT }));
    });
}

// Only clear auth on first run or if explicitly requested
// This allows reconnection without re-scanning QR code
// To force new QR, delete the auth directory manually

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();
    
    const sock = makeWASocket({
        version,
        auth: state,
        printQRInTerminal: false,
        logger: P({ level: 'silent' }), // Disable Baileys logs
        browser: ['Ubuntu', 'Chrome', '22.04.4']
    });
    currentSock = sock;
    startSendServer();

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;
        
        if (qr) {
            // Generate QR code as base64 data URL
            const qrDataURL = await qrcode.toDataURL(qr);
            console.log(JSON.stringify({ type: 'qr', data: qrDataURL }));
        }
        
        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error instanceof Boom) 
                ? lastDisconnect.error.output.statusCode !== DisconnectReason.loggedOut
                : true;
            
            console.log(JSON.stringify({ 
                type: 'status', 
                status: 'disconnected',
                shouldReconnect 
            }));
            
            if (shouldReconnect) {
                connectToWhatsApp();
            }
        } else if (connection === 'open') {
            const phoneNumber = sock.user?.id || 'unknown';
            console.log(JSON.stringify({ 
                type: 'status', 
                status: 'connected',
                phoneNumber: phoneNumber.split(':')[0]
            }));
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg.key.fromMe && m.type === 'notify') {
            const messageId = msg.key.id;
            const text = msg.message?.conversation
                || msg.message?.extendedTextMessage?.text
                || msg.message?.imageMessage?.caption
                || '';
            const messageData = {
                type: 'message',
                from: msg.key.remoteJid,
                text,
                hasImage: !!msg.message?.imageMessage,
                timestamp: new Date().toISOString(),
                message_id: messageId
            };
            console.log(JSON.stringify(messageData));
            
            // Send to backend for processing
            try {
                // If image, download and upload media first
                if (messageData.hasImage) {
                    let uploadId = null;
                    try {
                        const buffer = await downloadMediaMessage(
                            msg,
                            'buffer',
                            {},
                            { logger: P({ level: 'silent' }) }
                        );

                        const mimeType = msg.message?.imageMessage?.mimetype || 'image/jpeg';
                        const caption = msg.message?.imageMessage?.caption || '';
                        const fileExt = mimeType.includes('png') ? '.png' : (mimeType.includes('webp') ? '.webp' : '.jpg');
                        const filename = `${messageId || Date.now()}${fileExt}`;

                        const form = new FormData();
                        form.append('from', messageData.from);
                        form.append('message_id', messageId || '');
                        form.append('timestamp', messageData.timestamp);
                        form.append('mime_type', mimeType);
                        if (caption) form.append('caption', caption);
                        form.append('file', new Blob([buffer], { type: mimeType }), filename);

                        const mediaResp = await fetch('http://orchestrator:8000/api/v1/whatsapp/media', {
                            method: 'POST',
                            headers: INTERNAL_KEY ? { 'X-UASK-INTERNAL-KEY': INTERNAL_KEY } : {},
                            body: form
                        });

                        const mediaJson = await mediaResp.json();
                        uploadId = mediaJson.upload_id;
                    } catch (err) {
                        console.error('Error uploading image:', err);
                        await sock.sendMessage(msg.key.remoteJid, {
                            text: 'Could not upload the image. Please resend.'
                        });
                        return;
                    }

                    if (uploadId) {
                        messageData.upload_id = uploadId;
                    }
                }

                const response = await fetch('http://orchestrator:8000/api/v1/whatsapp/message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(messageData)
                });
                const result = await response.json();
                
                if (result.reply) {
                    await sock.sendMessage(msg.key.remoteJid, { text: result.reply });
                }
            } catch (error) {
                console.error('Error processing message:', error);
                await sock.sendMessage(msg.key.remoteJid, { 
                    text: 'Sorry, I encountered an error processing your message. Please try again.' 
                });
            }
        }
    });

    return sock;
}

// Handle process termination
process.on('SIGINT', () => {
    console.log(JSON.stringify({ type: 'status', status: 'shutdown' }));
    process.exit(0);
});

connectToWhatsApp();
"""
        
        # Save the script to a temporary location
        script_dir = os.path.join(tempfile.gettempdir(), 'whatsapp_bot')
        os.makedirs(script_dir, exist_ok=True)
        
        self.node_script_path = os.path.join(script_dir, 'whatsapp_bot.js')
        with open(self.node_script_path, 'w') as f:
            f.write(script_content)
        
        print(f"[WhatsApp] Node.js script created at {self.node_script_path}")

    def _ensure_node_deps(self, script_dir: str) -> Optional[str]:
        """Ensure required Node.js deps are installed in the script directory."""
        required = ["@whiskeysockets/baileys", "@hapi/boom", "qrcode", "pino"]
        node_modules = os.path.join(script_dir, "node_modules")

        def has_pkg(pkg: str) -> bool:
            if pkg.startswith("@"):
                scope, name = pkg.split("/", 1)
                return os.path.isdir(os.path.join(node_modules, scope, name))
            return os.path.isdir(os.path.join(node_modules, pkg))

        if all(has_pkg(pkg) for pkg in required):
            return None

        try:
            if not os.path.isdir(script_dir):
                os.makedirs(script_dir, exist_ok=True)

            env = os.environ.copy()
            # Ensure npm can write cache/logs in read-only container filesystems.
            env.setdefault("HOME", "/tmp")
            env.setdefault("NPM_CONFIG_CACHE", "/tmp/.npm")

            # Initialize npm project if needed (keeps installs local to script_dir).
            if not os.path.isfile(os.path.join(script_dir, "package.json")):
                subprocess.run(
                    ["npm", "init", "-y"],
                    cwd=script_dir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env,
                )

            install_cmd = ["npm", "install", *required]
            subprocess.run(
                install_cmd,
                cwd=script_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            return None
        except Exception as e:
            return f"Failed to install Node.js deps: {e}"

    async def initialize(self) -> Dict[str, Any]:
        """Start the WhatsApp bot and generate QR code"""
        if self.status in ["connecting", "connected", "qr_ready"]:
            return self.get_status()
        
        try:
            self.status = "connecting"
            script_dir = os.path.dirname(self.node_script_path)

            # If previously logged out, clear auth to force a fresh QR code.
            if self.logged_out:
                auth_dir = os.path.join(script_dir, "whatsapp_auth")
                try:
                    if os.path.isdir(auth_dir):
                        import shutil
                        shutil.rmtree(auth_dir, ignore_errors=True)
                    self.logged_out = False
                    self.error = None
                except Exception as e:
                    self.status = "disconnected"
                    return {
                        "status": "disconnected",
                        "error": f"Failed to reset WhatsApp auth: {e}",
                    }

            install_error = self._ensure_node_deps(script_dir)
            if install_error:
                self.status = "disconnected"
                return {
                    "status": "disconnected",
                    "error": install_error,
                }
            
            # Set NODE_PATH to include global npm modules
            env = os.environ.copy()
            if "NODE_PATH" not in env:
                try:
                    npm_root = subprocess.check_output(["npm", "root", "-g"], text=True).strip()
                    if npm_root:
                        env["NODE_PATH"] = npm_root
                except Exception:
                    pass
            
            # Start the Node.js process
            self.process = subprocess.Popen(
                ['node', self.node_script_path],
                cwd=script_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env
            )
            
            # Start monitoring output in background with asyncio thread executor
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self._monitor_process_sync)
            
            print("[WhatsApp] Bot initialization started")
            return self.get_status()
            
        except Exception as e:
            print(f"[WhatsApp] Initialization error: {e}")
            import traceback
            traceback.print_exc()
            self.status = "disconnected"
            return {
                "status": "disconnected",
                "error": f"Failed to initialize: {str(e)}"
            }

    def _monitor_process_sync(self):
        """Monitor the Node.js process output (runs in thread)"""
        if not self.process:
            print("[WhatsApp] No process to monitor")
            return
        
        try:
            print("[WhatsApp] Starting process monitor")
            print(f"[WhatsApp] Process PID: {self.process.pid}")
            
            # Monitor both stdout and stderr
            import threading
            
            def monitor_stderr():
                if self.process.stderr:
                    for line in self.process.stderr:
                        line = line.strip()
                        if line:
                            print(f"[WhatsApp] STDERR: {line}")
            
            stderr_thread = threading.Thread(target=monitor_stderr, daemon=True)
            stderr_thread.start()
            
            # Monitor stdout
            if self.process.stdout:
                for line in self.process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    
                    print(f"[WhatsApp] STDOUT: {line}")
                    
                    try:
                        data = json.loads(line)
                        msg_type = data.get('type')
                        
                        if msg_type == 'qr':
                            self.qr_code = data.get('data')
                            self.status = "qr_ready"
                            print("[WhatsApp] QR code generated successfully")
                        
                        elif msg_type == 'status':
                            new_status = data.get('status')
                            if new_status == 'connected':
                                self.status = "connected"
                                self.phone_number = data.get('phoneNumber')
                                self.qr_code = None
                                self.error = None
                                self.logged_out = False
                                print(f"[WhatsApp] Connected: {self.phone_number}")
                            elif new_status == 'disconnected':
                                self.status = "disconnected"
                                self.qr_code = None
                                if data.get("shouldReconnect") is False:
                                    self.logged_out = True
                                    self.error = "WhatsApp logged out. Re-initialize to generate a new QR code."
                                print("[WhatsApp] Disconnected")
                        
                        elif msg_type == 'message':
                            self.messages_count += 1
                            self.last_message_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            print(f"[WhatsApp] Message received from {data.get('from')}")
                    
                    except json.JSONDecodeError:
                        print(f"[WhatsApp] Non-JSON output: {line}")
            
            print("[WhatsApp] Process monitor ended")
        
        except Exception as e:
            print(f"[WhatsApp] Monitor error: {e}")
            import traceback
            traceback.print_exc()

    async def disconnect(self) -> Dict[str, Any]:
        """Disconnect the WhatsApp bot"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        
        self.status = "disconnected"
        self.qr_code = None
        self.phone_number = None
        self.error = None
        self.logged_out = False
        print("[WhatsApp] Bot disconnected")
        
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return {
            "status": self.status,
            "qrCode": self.qr_code,
            "phoneNumber": self.phone_number,
            "messagesCount": self.messages_count,
            "lastMessageAt": self.last_message_at,
            "error": self.error,
        }

# Singleton instance
whatsapp_service = WhatsAppService()
