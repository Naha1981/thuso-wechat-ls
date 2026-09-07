# THUSO Food Web

Mobile-first customer shell for the THUSO Food + Delivery vertical.

## Principles

- Low-bandwidth first: no image-heavy dependencies, no map SDK, minimal JavaScript.
- LSL-first pricing.
- WhatsApp remains the primary channel; this web surface is a fallback/companion.
- Delivery location is explicit and required before checkout.
- The frontend never contains payment-provider secrets.

## Run

Set `NEXT_PUBLIC_API_BASE` to the THUSO API base, then run `npm install` and `npm run dev`.
