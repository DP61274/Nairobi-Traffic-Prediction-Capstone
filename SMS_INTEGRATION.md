# Africa's Talking SMS Integration

Phase 2 adds SMS as a lightweight transport layer over the same backend used by the web form and chatbot:

```text
SMS -> webhook -> parser -> normalize_location(...) -> predict_route(...) -> SMS formatter
```

The SMS layer does not duplicate geocoding, ML inference, ETA lookup, confidence scoring, or advice generation.

## Sandbox Shortcode Defaults

Use these values for Africa's Talking Sandbox shortcode testing:

```env
AT_USERNAME=sandbox
AT_API_KEY=your_africastalking_sandbox_api_key
AT_SHORTCODE=61274
AT_SMS_KEYWORD=TRAFFIC
AT_SMS_MODE=premium
AT_SMS_API_URL=https://content.africastalking.com/version1/messaging
```

`AT_SMS_MODE=premium` is the default because this project uses shortcode + keyword two-way SMS. Premium replies include `from`, `keyword`, `bulkSMSMode=0`, and `linkId` when Africa's Talking sends one.

For simple legacy sandbox/bulk-style reply testing, use:

```env
AT_SMS_MODE=legacy
AT_SMS_API_URL=https://api.africastalking.com/version1/messaging
```

Do not use `https://api.sandbox.africastalking.com/version1/messaging`; the official live endpoints accept sandbox credentials and route them correctly.

## Webhook URL

On Render, configure Africa's Talking incoming SMS callbacks to:

```text
https://your-render-app.onrender.com/sms/africastalking/
```

## Sandbox Setup

1. Use app name `Sandbox`.
2. Configure shortcode `61274`.
3. Configure keyword `TRAFFIC`.
4. Set the incoming SMS callback URL to `/sms/africastalking/`.

## Supported SMS Formats

```text
TRAFFIC
Westlands*JKIA*NOW
CBD*Karen*NOW*TOLL
Kasarani*Upperhill*NOW*SCHOOL
Westlands*JKIA*MONDAY*17*LIGHT
CBD*Karen*FRIDAY*8*HEAVY*SCHOOL
Kilimani*Thika Road Mall*SUNDAY*14*DRY*TOLL
```

Weather values are controlled:

```text
DRY
LIGHT RAIN
HEAVY RAIN
```

Short forms `SUNNY`, `LIGHT`, and `HEAVY` are normalized for user convenience.

## Moving To A Live Hackathon Shortcode

On hackathon day, change only the Africa's Talking environment values:

```env
AT_USERNAME=your_live_app_username
AT_API_KEY=your_live_api_key
AT_SHORTCODE=your_live_shortcode
AT_SMS_KEYWORD=your_live_keyword
AT_SMS_MODE=premium
AT_SMS_API_URL=https://content.africastalking.com/version1/messaging
```

No prediction, geocoding, chatbot, form, or map code needs to change.
