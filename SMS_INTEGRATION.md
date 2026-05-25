# Africa's Talking SMS Sandbox

Phase 2 adds a lightweight SMS transport layer over the same prediction engine used by the web form and chatbot.

## Sandbox Defaults

```env
AT_USERNAME=sandbox
AT_SHORTCODE=61274
AT_SMS_KEYWORD=TRAFFIC
AT_SMS_API_URL=https://api.sandbox.africastalking.com/version1/messaging
AT_API_KEY=your_africastalking_sandbox_api_key
```

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

## Moving To Live

To move from Sandbox to a live hackathon shortcode later, update only the Africa's Talking environment variables:

```env
AT_USERNAME=your_live_username
AT_API_KEY=your_live_api_key
AT_SHORTCODE=your_live_shortcode
AT_SMS_KEYWORD=your_live_keyword
AT_SMS_API_URL=https://api.africastalking.com/version1/messaging
```

No prediction, geocoding, chatbot, or map code needs to change.
