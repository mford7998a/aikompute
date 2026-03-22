# Setting up Admin Access for the Main Dashboard

The Web Dashboard powered by the FastAPI Gateway does **NOT** have a default hardcoded admin username or password for security reasons.

To gain access to the admin dashboard, you must register a normal account and then manually grant it admin privileges in the database.

## Instructions

1. Open your web browser and go to your main site (e.g., `https://aikompute.com/`).
2. Click **Register** and create a new account using an email address and a password of your choosing.
3. SSH into your GCP server where the application is running.
4. Run the following command exactly to update your new account so it possesses admin rights:

   ```bash
   sudo docker exec inference-db psql -U inference -d inference_gateway -c "UPDATE users SET is_admin = true WHERE email = 'YOUR_EMAIL@example.com';"
   ```

   *(Make sure to replace `YOUR_EMAIL@example.com` with the email you registered in Step 2)*
   
5. Navigate to `https://aikompute.com/admin.html` in your browser.
6. Log in using the email and password you just created. You should now have full admin access!


---

### Note on other credentials seen in setup scripts:
The credentials sometimes printed out by `vm_setup.sh` (like `admin` / `Rk7mQ4vX9nL2p`) belong to a **separate internal sub-system** (Antigravity2API) and do not apply to this web dashboard.
