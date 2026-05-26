import fs from "fs";
import path from "path";

function loadRootEnv() {
  const envPath = path.resolve(process.cwd(), "../.env");
  if (!fs.existsSync(envPath)) return {};
  const vars = {};
  for (const line of fs.readFileSync(envPath, "utf8").split("\n")) {
    const match = line.match(/^([^#=]+)=(.*)$/);
    if (match) vars[match[1].trim()] = match[2].trim();
  }
  return vars;
}

const rootEnv = loadRootEnv();

/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: rootEnv.BACKEND_URL ?? "http://localhost:8000",
  },
  async rewrites() {
    return [
      {
        source: "/audio/:path*",
        destination: "http://localhost:8000/audio/:path*",
      },
    ];
  },
};

export default nextConfig;
