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
const crypto = require('crypto');
const katex = require('katex');
const sharp = require('sharp');
const { mathjax } = require('mathjax-full/js/mathjax.js');
const { TeX } = require('mathjax-full/js/input/tex.js');
const { MathML } = require('mathjax-full/js/input/mathml.js');
const { SVG } = require('mathjax-full/js/output/svg.js');
const { liteAdaptor } = require('mathjax-full/js/adaptors/liteAdaptor.js');
const { RegisterHTMLHandler } = require('mathjax-full/js/handlers/html.js');
const { AllPackages } = require('mathjax-full/js/input/tex/AllPackages.js');

const AUTH_DIR = process.env.WHATSAPP_AUTH_DIR || path.join(__dirname, 'whatsapp_auth');
const CACHE_DIR = process.env.WHATSAPP_LATEX_CACHE_DIR || '/app/storage/latex_cache';

// Ensure auth directory exists (persistent if WHATSAPP_AUTH_DIR points to /app/storage)
try {
    if (!fs.existsSync(AUTH_DIR)) {
        fs.mkdirSync(AUTH_DIR, { recursive: true });
    }
} catch (e) {
    console.error('Failed to ensure AUTH_DIR:', e);
}

// Ensure cache directory exists
try {
    if (!fs.existsSync(CACHE_DIR)) {
        fs.mkdirSync(CACHE_DIR, { recursive: true });
    }
} catch (e) {
    console.error('Failed to ensure CACHE_DIR:', e);
}

const INTERNAL_KEY = process.env.WHATSAPP_INTERNAL_KEY || '';
const INTERNAL_PORT = process.env.WHATSAPP_INTERNAL_PORT || '8791';
let currentSock = null;
let sendServerStarted = false;

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const svgOutput = new SVG({ fontCache: 'none' });
const texInput = new TeX({ packages: AllPackages });
const mathmlInput = new MathML({});
const texDoc = mathjax.document('', { InputJax: texInput, OutputJax: svgOutput });
const mathmlDoc = mathjax.document('', { InputJax: mathmlInput, OutputJax: svgOutput });

function normalizeLatex(latex) {
    return (latex || '').trim().replace(/\\s+/g, ' ');
}

function extractSvg(markup) {
    const match = String(markup || '').match(/<svg[^>]*>[\\s\\S]*<\\/svg>/);
    return match ? match[0] : markup;
}

function latexCacheKey(latex, engine, format, displayMode, scale) {
    const normalized = normalizeLatex(latex);
    const raw = `${engine}|${format}|${displayMode ? 1 : 0}|${scale}|${normalized}`;
    return crypto.createHash('sha256').update(raw).digest('hex');
}

function renderWithMathJaxTex(latex, displayMode) {
    const node = texDoc.convert(latex, { display: displayMode });
    return adaptor.outerHTML(node);
}

function renderWithMathJaxMathML(mathml, displayMode) {
    const node = mathmlDoc.convert(mathml, { display: displayMode });
    return adaptor.outerHTML(node);
}

function renderWithKatex(latex, displayMode) {
    const mathml = katex.renderToString(latex, {
        displayMode,
        throwOnError: false,
        output: 'mathml'
    });
    return renderWithMathJaxMathML(mathml, displayMode);
}

async function renderLatexToImage(latex, format, scale, displayMode, engine) {
    const envScale = Number(process.env.WHATSAPP_LATEX_SCALE || '2');
    const safeScale = Math.max(1, Math.min(3, scale || envScale || 2));
    const maxWidth = Number(process.env.WHATSAPP_LATEX_MAX_WIDTH || '900');
    const maxHeight = Number(process.env.WHATSAPP_LATEX_MAX_HEIGHT || '0');
    let svg = '';
    try {
        if (engine === 'mathjax') {
            svg = renderWithMathJaxTex(latex, displayMode);
        } else {
            svg = renderWithKatex(latex, displayMode);
        }
    } catch (err) {
        if (engine !== 'mathjax') {
            svg = renderWithMathJaxTex(latex, displayMode);
        } else {
            throw err;
        }
    }

    svg = extractSvg(svg);
    const density = 110 * safeScale;
    let img = sharp(Buffer.from(svg), { density }).flatten({ background: '#ffffff' }).toFormat(format);
    if ((maxWidth && Number.isFinite(maxWidth)) || (maxHeight && Number.isFinite(maxHeight))) {
        img = img.resize({
            width: maxWidth && Number.isFinite(maxWidth) ? maxWidth : null,
            height: maxHeight && Number.isFinite(maxHeight) ? maxHeight : null,
            fit: 'inside',
            withoutEnlargement: true,
        });
    }
    const buffer = await img.toBuffer();
    const meta = await sharp(buffer).metadata();
    return { buffer, width: meta.width || 0, height: meta.height || 0, svg };
}

function readJson(req) {
    return new Promise((resolve, reject) => {
        let body = '';
        req.on('data', chunk => {
            body += chunk;
            if (body.length > 10 * 1024 * 1024) {
                reject(new Error('Payload too large'));
            }
        });
        req.on('end', () => {
            try {
                resolve(JSON.parse(body || '{}'));
            } catch (err) {
                reject(err);
            }
        });
    });
}

function startSendServer() {
    if (sendServerStarted) return;
    sendServerStarted = true;

    const server = http.createServer(async (req, res) => {
        if (req.method !== 'POST') {
            res.statusCode = 404;
            return res.end('Not found');
        }

        if (INTERNAL_KEY && req.headers['x-uask-internal-key'] !== INTERNAL_KEY) {
            res.statusCode = 401;
            return res.end('Unauthorized');
        }

        if (!currentSock) {
            res.statusCode = 503;
            return res.end('WhatsApp not connected');
        }

        if (req.url === '/send') {
            try {
                const payload = await readJson(req);
                const to = payload.to;
                const text = payload.text;
                if (!to || !text) {
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
        }

        if (req.url === '/send-media') {
            try {
                const payload = await readJson(req);
                const to = payload.to;
                const bytesBase64 = payload.bytesBase64;
                const contentType = payload.contentType || 'image/webp';
                const caption = payload.caption || '';
                if (!to || !bytesBase64) {
                    res.statusCode = 400;
                    return res.end('Bad request');
                }
                const buffer = Buffer.from(bytesBase64, 'base64');
                await currentSock.sendMessage(to, { image: buffer, mimetype: contentType, caption });
                res.statusCode = 200;
                return res.end('OK');
            } catch (err) {
                res.statusCode = 500;
                return res.end('Error');
            }
        }

        if (req.url === '/internal/latex/render') {
            try {
                const payload = await readJson(req);
                const latex = normalizeLatex(payload.latex || '');
                const format = (payload.format || 'webp').toLowerCase();
                const displayMode = payload.displayMode !== false;
                const scale = Number(payload.scale) || 2;
                const engine = (payload.engine || 'katex').toLowerCase();
                const returnSvg = payload.returnSvg === true || format === 'svg';
                if (!latex) {
                    res.statusCode = 400;
                    return res.end('Bad request');
                }

                const key = latexCacheKey(latex, engine, format, displayMode, scale);
                const cachePath = path.join(CACHE_DIR, `${key}.${format}`);
                const svgCachePath = path.join(CACHE_DIR, `${key}.svg`);

                if (format === 'svg' && fs.existsSync(svgCachePath)) {
                    const svgCached = fs.readFileSync(svgCachePath);
                    res.statusCode = 200;
                    res.setHeader('Content-Type', 'application/json');
                    return res.end(JSON.stringify({
                        contentType: 'image/svg+xml',
                        svgBase64: svgCached.toString('base64'),
                        svgContentType: 'image/svg+xml'
                    }));
                }
                if (format !== 'svg' && fs.existsSync(cachePath)) {
                    const cached = fs.readFileSync(cachePath);
                    let svgBase64 = null;
                    if (returnSvg && fs.existsSync(svgCachePath)) {
                        svgBase64 = fs.readFileSync(svgCachePath).toString('base64');
                    }
                    res.statusCode = 200;
                    res.setHeader('Content-Type', 'application/json');
                    return res.end(JSON.stringify({
                        contentType: `image/${format}`,
                        bytesBase64: cached.toString('base64'),
                        svgBase64: svgBase64 || undefined,
                        svgContentType: svgBase64 ? 'image/svg+xml' : undefined
                    }));
                }

                if (format === 'svg') {
                    const svg = extractSvg(engine === 'mathjax' ? renderWithMathJaxTex(latex, displayMode) : renderWithKatex(latex, displayMode));
                    fs.writeFileSync(svgCachePath, svg);
                    res.statusCode = 200;
                    res.setHeader('Content-Type', 'application/json');
                    return res.end(JSON.stringify({
                        contentType: 'image/svg+xml',
                        svgBase64: Buffer.from(svg).toString('base64'),
                        svgContentType: 'image/svg+xml'
                    }));
                }

                const { buffer, width, height, svg } = await renderLatexToImage(latex, format, scale, displayMode, engine);
                fs.writeFileSync(cachePath, buffer);
                if (returnSvg && svg) {
                    fs.writeFileSync(svgCachePath, svg);
                }
                res.statusCode = 200;
                res.setHeader('Content-Type', 'application/json');
                return res.end(JSON.stringify({
                    contentType: `image/${format}`,
                    bytesBase64: buffer.toString('base64'),
                    svgBase64: returnSvg && svg ? Buffer.from(svg).toString('base64') : undefined,
                    svgContentType: returnSvg && svg ? 'image/svg+xml' : undefined,
                    width,
                    height
                }));
            } catch (err) {
                console.error('Latex render error:', err);
                res.statusCode = 500;
                res.setHeader('Content-Type', 'application/json');
                return res.end(JSON.stringify({ error: String(err && err.message ? err.message : err) }));
            }
        }

        res.statusCode = 404;
        return res.end('Not found');
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
        
        # Save the script to a writable, exec-friendly location
        script_root = os.environ.get("WHATSAPP_NODE_DIR", "/app/storage/whatsapp_bot")
        script_dir = os.path.join(script_root)
        os.makedirs(script_dir, exist_ok=True)
        
        self.node_script_path = os.path.join(script_dir, 'whatsapp_bot.js')
        with open(self.node_script_path, 'w') as f:
            f.write(script_content)
        
        print(f"[WhatsApp] Node.js script created at {self.node_script_path}")

    def _ensure_node_deps(self, script_dir: str) -> Optional[str]:
        """Ensure required Node.js deps are installed in the script directory."""
        required = ["@whiskeysockets/baileys", "@hapi/boom", "qrcode", "pino", "katex", "sharp", "mathjax-full"]
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

            # Ensure no stale Node process is holding the internal port.
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None

            # If previously logged out, clear auth to force a fresh QR code.
            if self.logged_out:
                auth_dir = os.environ.get("WHATSAPP_AUTH_DIR") or os.path.join(script_dir, "whatsapp_auth")
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
