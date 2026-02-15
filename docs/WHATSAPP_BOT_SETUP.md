# WhatsApp Bot Integration Guide

## Overview
The WhatsApp Bot allows students to interact with the uask.ai math tutor directly from their mobile phones via WhatsApp. Students can send math problems as text or photos and receive step-by-step solutions instantly.

## Features
- ✅ Real-time math problem solving via WhatsApp
- ✅ Text and image-based problem support (image OCR coming soon)
- ✅ User verification with unique secret codes
- ✅ Subscription-based access control
- ✅ Mobile-optimized responses
- ✅ Usage tracking and analytics

## Setup Instructions

### 1. Database Migration
First, add the WhatsApp integration fields to your database:

```bash
cd backend
python add_whatsapp_columns.py
```

This script will:
- Add `whatsapp_number`, `whatsapp_secret`, and `whatsapp_enabled` columns to the User table
- Generate unique 8-character verification codes for all existing users

### 2. WhatsApp Prompt Configuration
Add the WhatsApp-specific prompt template to the database:

```bash
cd backend
python add_whatsapp_prompt.py
```

This creates a mobile-optimized prompt template that:
- Keeps responses concise (under 500 words)
- Uses WhatsApp-friendly formatting
- Includes emojis for engagement
- Focuses on mobile readability

### 3. Install Node.js Dependencies
The WhatsApp service requires Baileys library and its dependencies:

```bash
# These are installed automatically when the bot initializes
# But you can pre-install them:
cd /tmp/whatsapp_bot  # Or wherever the service creates its working directory
npm install @whiskeysockets/baileys @hapi/boom qrcode
```

### 4. Backend Setup
The WhatsApp service is already integrated into your FastAPI backend. Make sure your backend is running:

```bash
cd backend
docker compose up orchestrator
```

### 5. Frontend Access
The WhatsApp Bot management interface is available in the Admin Panel:
- Navigate to `/admin/whatsapp-bot`
- Click "Initialize Connection" to start the bot
- Scan the QR code with your WhatsApp app
- Monitor connection status and statistics

## User Flow

### For Administrators
1. Go to Admin Panel → WhatsApp Bot
2. Click "Initialize Connection"
3. Open WhatsApp on your phone → Settings → Linked Devices
4. Tap "Link a Device" and scan the QR code
5. Once connected, the bot is live and ready to receive messages

### For Students
1. Go to Settings → Preferences
2. Find "WhatsApp Integration" section
3. Click the eye icon to reveal your unique verification code
4. Copy the code
5. Save the WhatsApp bot number (ask admin for the number)
6. Send a message: `CODE YOUR-CODE-HERE`
7. Once verified, send math problems directly!

## API Endpoints

### Admin Endpoints
- `GET /api/v1/admin/whatsapp/status` - Get bot connection status
- `POST /api/v1/admin/whatsapp/initialize` - Start bot and generate QR code
- `POST /api/v1/admin/whatsapp/disconnect` - Disconnect bot

### Message Handler
- `POST /api/v1/whatsapp/message` - Process incoming WhatsApp messages
  - Verifies user with secret code
  - Checks subscription status
  - Solves math problems
  - Returns formatted responses

## Security Features

### User Verification
- Each student gets a unique 8-character alphanumeric code
- Code is required on first message from any phone number
- Code is hidden by default in student settings (eye icon to reveal)
- Once verified, phone number is linked to their account

### Subscription Checks
- Bot verifies active subscription before processing messages
- Non-subscribers receive a friendly message to upgrade
- Usage is tracked and logged for billing

### Privacy
- Phone numbers are stored securely
- Only verified numbers can access the service
- Students can disable WhatsApp integration anytime

## Message Format

### Text Problems
Students can simply type or paste their math problems:
```
What is the derivative of x^2 + 3x + 5?
```

### Image Problems (Coming Soon)
Students can send photos of math problems. Currently, the bot will acknowledge images and ask for text input. Full OCR support is planned.

### Response Format
The bot sends mobile-optimized responses:
```
📝 *Problem:* What is the derivative of x^2 + 3x + 5?

*Solution Steps:*

*1. Identify the Function*
We have f(x) = x² + 3x + 5

*2. Apply Power Rule*
Derivative: f'(x) = 2x + 3

✅ *Answer:* f'(x) = 2x + 3

💡 _Need more help? Visit uask.ai_
```

## Troubleshooting

### QR Code Not Appearing
- Check that the orchestrator container is running
- Verify Node.js is installed in the container
- Check backend logs: `docker compose logs orchestrator`

### Bot Not Responding
- Verify the bot is connected (check Admin Panel status)
- Check that the phone hasn't logged out from WhatsApp
- Restart the bot: disconnect and reconnect

### User Can't Verify
- Ensure they're copying the code exactly (no spaces)
- Code is case-sensitive (all uppercase + digits)
- Check that their account is active
- Verify they have an active subscription

### Messages Not Being Received
- Check the webhook is accessible from the Node.js process
- Verify the orchestrator container can reach itself on port 8000
- Check for errors in backend logs

## Technical Architecture

### Components
1. **Next.js Frontend**
   - Admin panel UI (`/admin/whatsapp-bot`)
   - Student settings UI (`/profile` → Preferences tab)
   - API proxy routes (`/api/admin/whatsapp/*`)

2. **FastAPI Backend**
   - WhatsApp service (`backend/app/services/whatsapp/`)
   - API endpoints (`backend/app/api.py`)
   - User model with WhatsApp fields (`backend/app/models.py`)
   - WhatsApp-specific prompts in database

3. **Node.js Process**
   - Baileys library for WhatsApp connection
   - QR code generation
   - Message event handling
   - Webhook to FastAPI backend

### Data Flow
```
WhatsApp → Baileys (Node.js) → FastAPI Backend → Solver Service → OpenAI → Response → Baileys → WhatsApp
```

### Database Schema
New fields in `user` table:
- `whatsapp_number` (VARCHAR, indexed) - Verified phone number
- `whatsapp_secret` (VARCHAR) - 8-character verification code
- `whatsapp_enabled` (BOOLEAN) - Enable/disable bot access

## Future Enhancements
- [ ] Full image OCR support for photo-based problems
- [ ] Multi-turn conversations (follow-up questions)
- [ ] Voice message support
- [ ] Group chat support for study groups
- [ ] Advanced analytics and insights
- [ ] Multiple language support
- [ ] Rich media responses (graphs, diagrams)

## Support
For issues or questions:
- Check the Admin Panel for connection status
- Review backend logs for errors
- Contact technical support with error details
- Refer to Baileys documentation: https://github.com/WhiskeySockets/Baileys

## Notes
- The bot uses a separate Node.js process managed by Python
- QR codes expire after a few minutes - regenerate if needed
- Only one device can be connected at a time
- WhatsApp Terms of Service apply - use responsibly
- Rate limiting may apply based on WhatsApp's policies
