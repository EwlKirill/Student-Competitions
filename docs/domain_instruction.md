# Buying a `.org` Domain for Login Emails

## Why the project needs a domain

Milestone 4 sends login codes by email through [Resend](https://resend.com) over its HTTPS API.
The API is used instead of SMTP because free Render web services block outbound SMTP ports.
Without a verified domain, Resend delivers only to the Resend account owner's own address. That
blocks multi-user testing from milestone 5 on. A domain bought early also builds sending
reputation before real users arrive.

`.org` fits a non-commercial service for students. Anyone can register one: you don't need
nonprofit status or any documents.

## Price

Prices below are from third-party price trackers as of September 2026. Check the exact amount at
checkout.

| Registrar | First year | Renewal |
|---|---|---|
| **Cloudflare** (at cost, no markup) | ~$8.50 | ~$11.20 |
| Porkbun | ~$6.98 | ~$11.84 |

Cloudflare is the suggested registrar because it includes free DNS. The records needed for
Resend (and optionally Render) are then managed in the same dashboard.

## 1. Buy the domain on Cloudflare

1. **Create an account** at [dash.cloudflare.com](https://dash.cloudflare.com). It's free.
2. **Find the name.** Open **Domain Registration → Register Domains** and search for a name, e.g.
   `studentcompetitions.org`. Short, hyphen-free names are easier to type into an email address.
3. **Choose 1 year** (renewal is at cost anyway) and add a payment method (card or PayPal).
4. **Fill in the registrant contact** with your real name and email. The public WHOIS record hides
   it automatically.
5. **Check that auto-renew is on.** It is by default. An expired domain means nobody can log in.
6. **⚠️ Confirm the verification email.** ICANN requires the registrant's contact address to be
   verified. **If the email is not confirmed within 15 days, the domain is suspended.**

The domain then appears in the Cloudflare account with DNS already active.

## 2. Add the sending domain in Resend

1. In Resend, open **Domains → Add domain** and enter a **subdomain**, e.g.
   `mail.yourdomain.org`. Resend recommends a subdomain because it keeps email reputation
   separate from the root domain.
2. Choose the **EU region (Ireland)**, since the app (Render) and the database (Neon) are in
   Frankfurt.
3. Resend shows 3–4 DNS records: an MX record and an SPF TXT record for the return path, plus a
   DKIM TXT record (`resend._domainkey…`).

## 3. Add the DNS records in Cloudflare

1. Open Cloudflare → your domain → **DNS → Records** and copy each Resend record exactly.
2. Add a **DMARC** record, which Gmail and Yahoo expect:
   - Type: `TXT`
   - Name: `_dmarc`
   - Value: `v=DMARC1; p=none;` (can be made stricter later)
3. Back in Resend, click **Verify**. On Cloudflare this usually passes within minutes.

## 4. Test delivery

- Send a test email to a Gmail address. Open it, choose **⋮ → Show original**, and check that
  SPF, DKIM and DMARC all show **PASS**.
- Optionally, send one to [mail-tester.com](https://www.mail-tester.com) for a deliverability
  score.
- If possible, send one to an institutional (Microsoft 365) mailbox, since that is where students
  receive their codes.

## 5. Connect to the app

1. Create a Resend API key with **"Sending access"** permission only, limited to this domain.
2. Declare `RESEND_API_KEY` and `EMAIL_FROM` (e.g.
   `Student Competitions <login@mail.yourdomain.org>`) as `sync: false` env vars in
   [`render.yaml`](../render.yaml). Enter their values in the Render dashboard, the same way as
   `DATABASE_URL`.

## Optional: use the domain for the website

In Render, open the service's **Settings → Custom Domains**, add e.g. `app.yourdomain.org`, and
create the CNAME record Render shows. In Cloudflare, set that record to **"DNS only"** (grey
cloud) so Render can issue the TLS certificate.

Spec 002 lists a custom domain for the app as out of scope, so this part needs a small spec
change. The email subdomain doesn't touch the app's address.

## Sources

- [Render: free web services no longer allow outbound SMTP](https://render.com/changelog/free-web-services-will-no-longer-allow-outbound-traffic-to-smtp-ports)
- [Resend pricing](https://resend.com/docs/knowledge-base/what-is-resend-pricing)
- [Cloudflare .org pricing (domainoffer.net)](https://domainoffer.net/tld/org/cloudflare)
- [Porkbun .org pricing (domainoffer.net)](https://domainoffer.net/tld/org/porkbun)
- [Cloudflare low-cost domain names](https://www.cloudflare.com/application-services/solutions/low-cost-domain-names/)
