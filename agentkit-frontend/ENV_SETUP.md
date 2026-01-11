# Frontend Environment Variables Setup

Create a `.env` file in the `agentkit-frontend` directory with the following configuration:

## Development (.env)

```env
# Backend URL for Vite dev server proxy
# Points to unified-backend on port 8000
BACKEND_URL=http://localhost:8000

# ChatKit API Configuration
VITE_SUPPORT_API_BASE=/support

# ChatKit Domain Key
# Get your domain key from: https://platform.openai.com/settings/organization/security/domain-allowlist
# For local development, you can use a placeholder
VITE_SUPPORT_CHATKIT_API_DOMAIN_KEY=domain_pk_693c238303948190bdc3822908786a3905e8f79a8bc4a973

# Optional: Override default ChatKit API URL
# VITE_SUPPORT_CHATKIT_API_URL=/support/chatkit

# Optional: Override default customer context URL
# VITE_SUPPORT_CUSTOMER_URL=/support/customer

# Optional: Custom greeting message
# VITE_SUPPORT_GREETING=Search for products for quote ...
```

## Production (.env.production)

For production builds, create a `.env.production` file:

```env
# Production backend URL (Docker service name when running in Docker Compose)
BACKEND_URL=http://unified-backend:8000

# Production ChatKit Domain Key (register your domain first)
VITE_SUPPORT_CHATKIT_API_DOMAIN_KEY=your_production_domain_key_here

# Production API base path
VITE_SUPPORT_API_BASE=/support
```

## Notes

1. **VITE_ Prefix**: Vite only exposes environment variables prefixed with `VITE_` to the client-side code.

2. **BACKEND_URL**: This is used by Vite's proxy configuration (`vite.config.ts`) and is NOT exposed to the client. It's only used during development.

3. **Domain Key**: Register your production domain at https://platform.openai.com/settings/organization/security/domain-allowlist before deploying.

4. **API Endpoints**: The frontend expects the backend to be available at the paths configured in `SUPPORT_API_BASE` (default: `/support`).

## Quick Setup

To create the `.env` file for local development:

```bash
cd agentkit-frontend
cat > .env << 'EOF'
BACKEND_URL=http://localhost:8000
VITE_SUPPORT_API_BASE=/support
VITE_SUPPORT_CHATKIT_API_DOMAIN_KEY=domain_pk_693c238303948190bdc3822908786a3905e8f79a8bc4a973
EOF
```

