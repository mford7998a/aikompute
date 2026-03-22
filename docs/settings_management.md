# Settings & Account Management

This document explains how to configure and manage your AIKompute account, update your profile, handle billing, and secure your API usage.

## 1. Profile Settings

To access your profile settings:
1. Log into the Dashboard.
2. Click on your profile icon in the top right corner.
3. Select **Settings**.

From here, you can:
- **Update your Name and Email address**. (Note: Changing your email will require re-verification).
- **Change Password**: Provide your current password and define a new one.
- **Enable Two-Factor Authentication (2FA)**: Add an extra layer of security to your account using an authenticator app.

## 2. API Key Management

Proper rotation and strict management of your API Keys is vital for security.

- **Viewing Keys**: Under the **API Keys** tab, you can see all your active keys. The list displays the key name, creation date, and last used date.
- **Revoking Keys**: If a key is compromised or no longer needed, click the trash can icon next to the key to revoke it immediately. Any application using a revoked key will immediately receive authentication errors.
- **Tracking Usage by Key**: Soon, you will be able to filter your dashboard analytics by specific API keys to see which application is driving the most usage.

## 3. Billing & Payments

AIKompute operates on a pay-as-you-go model with a pre-funded balance or monthly invoicing depending on your tier.

### Adding Funds
1. Navigate to the **Billing** tab.
2. Click **Add Funds**.
3. Select the amount and input your credit card details via our secure Stripe integration.
4. Auto-recharge can be enabled to automatically top up your balance when it falls below a specific threshold.

### Viewing Invoices
Monthly invoices and receipts for added funds are available in the **Invoices** section. You can download these as PDFs for your accounting team.

## 4. Usage Limits and Alerts

To prevent unexpected costs:
- **Hard Limits**: Set an absolute maximum spend per month. If this is hit, all API requests will return an error until the next billing cycle or until you raise the limit.
- **Soft Limits (Alerts)**: Set a notification threshold. When your spend reaches this dollar amount, you will receive an email alert, but your API keys will continue to function.

## 5. Team Management (Pro & Enterprise)

If you are on an upgraded plan, you can invite team members to share your organization's resources.
1. Go to **Team** in the settings.
2. Click **Invite Member**.
3. Enter their email and assign a role (Admin, Developer, Viewer).
   - **Admin**: Can manage billing, team, and API keys.
   - **Developer**: Can create and use API keys, and view logs.
   - **Viewer**: Can only view usage and logs.
