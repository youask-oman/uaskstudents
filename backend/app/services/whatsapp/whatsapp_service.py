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
        self._setup_node_script()

    def _setup_node_script(self):
        """Create the Node.js script that uses Baileys"""
        script_content = """
const { default: makeWASocket, DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const qrcode = require('qrcode');
const fs = require('fs');
const path = require('path');
const P = require('pino');

const AUTH_DIR = path.join(__dirname, 'whatsapp_auth');

// Clear auth state to force QR generation
if (fs.existsSync(AUTH_DIR)) {
    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
}

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
            const messageData = {
                type: 'message',
                from: msg.key.remoteJid,
                text: msg.message?.conversation || msg.message?.extendedTextMessage?.text || '',
                hasImage: !!msg.message?.imageMessage,
                timestamp: new Date().toISOString()
            };
            console.log(JSON.stringify(messageData));
            
            // Send to backend for processing
            try {
                const response = await fetch('http://orchestrator:8000/api/whatsapp/message', {
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

    async def initialize(self) -> Dict[str, Any]:
        """Start the WhatsApp bot and generate QR code"""
        if self.status in ["connecting", "connected", "qr_ready"]:
            return self.get_status()
        
        try:
            self.status = "connecting"
            script_dir = os.path.dirname(self.node_script_path)
            
            # Set NODE_PATH to include global npm modules
            env = os.environ.copy()
            env['NODE_PATH'] = '/usr/lib/node_modules'
            
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
                            print("[WhatsApp] ✓ QR code generated successfully")
                        
                        elif msg_type == 'status':
                            new_status = data.get('status')
                            if new_status == 'connected':
                                self.status = "connected"
                                self.phone_number = data.get('phoneNumber')
                                self.qr_code = None
                                print(f"[WhatsApp] ✓ Connected: {self.phone_number}")
                            elif new_status == 'disconnected':
                                self.status = "disconnected"
                                self.qr_code = None
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
        }

# Singleton instance
whatsapp_service = WhatsAppService()
