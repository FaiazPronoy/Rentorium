# CSE471_Project: Rentorium

## Module 1: User Authentication

### Feature 1: Signup
Allow users to register by providing their name, email, password, and confirmation password.

**Validation during signup:**
- Ensure uniqueness of email addresses associated with user accounts.
- Passwords must be at least 8 characters long.
- Passwords must contain at least one uppercase letter, one digit, and one special character.

### Feature 2: Sign In/Sign Out
Enable users to log in using their email and password. Provide users with the option to securely log out of their accounts.

**Error Handling:**
- Display an error message for invalid credentials if the user enters an incorrect email and password.

### Feature 3: Profile Management
Provide users with the ability to view, update, and delete their profile information.

**Users can:**
- View their personal info while logged in.

**Update Profile:**
- Users can update their personal information and add additional details.

**Email update validation:**
- Validate email updates to ensure that the entered email is not already associated with another user account.
- Display an error message and prompt the user to enter a different email if the provided email is already in use.

**Account deletion:**
- Users navigate to their profile.
- They select the option to delete their account.
- A confirmation popup appears, prompting the user to confirm the irreversible deletion process by clicking "Confirm" or to cancel by clicking "Cancel".
- Before confirmation, they have to provide their password for an extra layer of security.
- If the user clicks "Confirm", the account is deleted, and they are taken to the home page with a success message.
- If the user clicks "Cancel," the deletion process is canceled, and the user will remain on their profile page without any changes.

### Feature 4: Password Reset
Allow users to reset their password if forgotten.

**Password reset procedure:**
- Users can request a password reset link via email.
- Upon clicking the link, users can reset their password securely.

### Feature 5: Two-Step Verification
Enhance security by enabling two-step verification for user accounts.
