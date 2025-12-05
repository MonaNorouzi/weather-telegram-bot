# Admin Commands Reference

## Dynamic Premium User Management

As admin, you can now manage premium users **without restarting the bot**:

### Commands

#### Add Premium User
```
/addpremium USER_ID
```
**Example**: `/addpremium 123456789`

**What it does**:
- Instantly grants premium access
- Shows user details (name, username)
- Persists until restart

#### Remove Premium User
```
/removepremium USER_ID
```
**Example**: `/removepremium 123456789`

**What it does**:
- Instantly revokes premium access
- User returns to free tier limits

#### List All Premium Users
```
/listpremium
```
**What it shows**:
- All current premium users
- Names, usernames, and IDs
- Total count

#### Reload from .env File
```
/reloadpremium
```
**What it does**:
- Reads `.env` file
- Updates premium user list
- Useful after editing `.env`

---

## Important Notes

⚠️ **Persistence**: 
- Commands like `/addpremium` and `/removepremium` work **immediately** but reset on bot restart
- For permanent changes, also update your `.env` file:
  ```env
  PREMIUM_USER_IDS=123456789,987654321,555555555
  ```

✅ **Best Practice Workflow**:
1. **Quick Test**: Use `/addpremium` to test immediately
2. **Make Permanent**: Add to `.env` file
3. **No Restart Needed**: Bot already has the user!

OR

1. **Edit .env**: Add user IDs to file
2. **Reload**: Use `/reloadpremium` command
3. **Done**: No restart needed!

---

## How to Get User IDs

**Method 1**: Message [@userinfobot](https://t.me/userinfobot)
- Just start a chat with this bot
- It will send you your ID

**Method 2**: From bot logs
- When users interact with your bot
- Check logs for user IDs

---

## Usage Examples

### Scenario 1: Quick Premium Grant
```
You: /addpremium 123456789
Bot: ✅ Premium Added
     👤 User: Mona Norouzi
     🆔 ID: 123456789
     🌟 Total Premium: 1
```

### Scenario 2: Remove Access
```
You: /removepremium 123456789
Bot: ✅ Premium Removed
     🆔 ID: 123456789
     🌟 Remaining Premium: 0
```

### Scenario 3: After Editing .env
```
# Edit .env file to add: PREMIUM_USER_IDS=111,222,333

You: /reloadpremium
Bot: ✅ Premium Users Reloaded
     📊 Before: 1 users
     📊 After: 3 users
     🔄 Changes applied from .env
```

### Scenario 4: Check Current Premium Users
```
You: /listpremium
Bot: 🌟 Premium Users (3)
     
     • Mona Norouzi (@mona) - 123456789
     • John Doe (@john) - 987654321
     • Unknown User - 555555555
```

---

## Premium Features Recap

Premium users get:
- ✅ **Unlimited city subscriptions** (vs 3 for free)
- ✅ **Premium Support button** in settings
- ✅ No upgrade prompts
- ✅ Priority recognition

Free users get:
- ❌ Maximum 3 city subscriptions
- ❌ Upgrade prompts when at limit
- ✅ All core weather features
