import type { NextConfig } from "next";
import fs from "fs";
import path from "path";

// Load environment variables from parent directory .env
const parentEnvPath = path.resolve(__dirname, "..", ".env");
if (fs.existsSync(parentEnvPath)) {
  const envContent = fs.readFileSync(parentEnvPath, "utf-8");
  envContent.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith("#")) {
      const firstEqual = trimmed.indexOf("=");
      if (firstEqual !== -1) {
        const key = trimmed.slice(0, firstEqual).trim();
        const value = trimmed.slice(firstEqual + 1).trim();
        const cleanValue = value.replace(/^['"]|['"]$/g, "");
        if (!process.env[key]) {
          process.env[key] = cleanValue;
        }
      }
    }
  });
}

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
