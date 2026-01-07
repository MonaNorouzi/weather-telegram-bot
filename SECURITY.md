# Security Policy

## Supported Versions

Currently supported versions of Weather Route Planner:

| Version | Supported          |
| ------- | ------------------ |
| 2.1.x   | :white_check_mark: |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please follow responsible disclosure practices:

### How to Report

1. **DO NOT** open a public GitHub issue
2. **DO** send details privately via:
   - Email: Create an issue and request private disclosure
   - GitHub Security Advisories: Use the "Security" tab

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

### Response Time

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Varies by severity

## Security Best Practices

When deploying this bot, follow these security guidelines:

### Credentials Protection

- ✅ **Never commit** `.env` files
- ✅ **Use strong passwords** for PostgreSQL and Redis
- ✅ **Keep Telegram API credentials secure** (API_HASH, BOT_TOKEN)
- ✅ **Rotate credentials** periodically
- ✅ **Use different credentials** for production and development

### Database Security

```bash
# PostgreSQL
- Use strong database password
- Limit database access to localhost
- Enable SSL connections in production
- Regular backups

# Redis
REDIS_PASSWORD=your_strong_password_here
- Always set a Redis password
- Bind to localhost only
- Use firewall rules
```

### Network Security

- ✅ Deploy behind a reverse proxy (nginx, traefik)
- ✅ Use HTTPS for any web interfaces
- ✅ Implement rate limiting
- ✅ Use firewall rules to restrict access

### Proxy Configuration

If using proxy for Open-Meteo API:

```bash
# Use trusted proxy only
PROXY_URL=http://trusted-proxy:port

# Verify proxy is secure
# Don't use public/untrusted proxies
```

### Session Files

- ✅ **Protect** `*.session` files (contain user authentication)
- ✅ **Never commit** session files to git
- ✅ **Backup securely** if needed
- ✅ **Delete** when no longer needed

### Production Deployment

```bash
# Recommended practices:
1. Use environment variables for all secrets
2. Run bot as non-root user
3. Enable log rotation
4. Monitor for suspicious activity
5. Keep dependencies updated
```

### Updates

- ✅ **Update dependencies** regularly
- ✅ **Monitor security advisories** for Python packages
- ✅ **Test updates** in development first
- ✅ **Keep Docker images updated** if using containers

## Known Security Considerations

### Open-Meteo API

- Free public API, no authentication required
- No sensitive data transmitted
- Consider rate limiting in production

### Telegram API

- Requires API credentials (keep secure)
- Uses MTProto encryption
- Session files contain authentication tokens

### PostgreSQL

- Stores route graph and cached data
- No sensitive user information
- Use strong passwords and restrict access

### Redis

- Stores cached weather data
- Temporary data (expires automatically)
- Set password in production

## Vulnerability Disclosure Timeline

1. **Day 0**: Vulnerability reported
2. **Day 1-2**: Acknowledgment sent
3. **Day 3-7**: Assessment and verification
4. **Day 7-30**: Develop and test fix
5. **Day 30+**: Public disclosure (if applicable)

## Security Updates

Security updates are released as:
- **Critical**: Immediate patch release
- **High**: Within 7 days
- **Medium**: Next minor version
- **Low**: Next major version

## Hall of Fame

Thank you to security researchers who have responsibly disclosed vulnerabilities:

*No reports yet - be the first!*

---

## Questions?

For security questions not related to vulnerabilities, open a public issue with the `security` label.

**Last Updated**: January 2026  
**Version**: 2.1.0
