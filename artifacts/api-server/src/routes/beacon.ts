import { Router, type IRouter, type Request, type Response } from "express";

const router: IRouter = Router();
const BEACON_API = "http://localhost:8000";

async function proxyToBeacon(req: Request, res: Response, beaconPath: string) {
  try {
    const url = `${BEACON_API}${beaconPath}`;
    const resp = await fetch(url, {
      method: req.method,
      headers: { "Content-Type": "application/json" },
      body: req.method !== "GET" && req.method !== "HEAD" ? JSON.stringify(req.body) : undefined,
    });
    const data = await resp.json();
    res.status(resp.status).json(data);
  } catch (err) {
    res.status(502).json({ error: "Beacon API unavailable", detail: String(err) });
  }
}

// Phase 1 routes
router.get("/health", (req, res) => proxyToBeacon(req, res, "/health"));
router.get("/telemetry/latest", (req, res) => proxyToBeacon(req, res, "/telemetry/latest"));
router.get("/telemetry/historical", (req, res) => proxyToBeacon(req, res, "/telemetry/historical"));
router.get("/telemetry/history", (req, res) => proxyToBeacon(req, res, "/telemetry/history"));
router.get("/identities", (req, res) => proxyToBeacon(req, res, "/identities"));
router.get("/metrics", (req, res) => proxyToBeacon(req, res, "/metrics"));
router.post("/events", (req, res) => proxyToBeacon(req, res, "/events"));

// Field status document
router.get("/field/v1/status.json", (req, res) => proxyToBeacon(req, res, "/field/v1/status.json"));
router.post("/field/v1/verify", (req, res) => proxyToBeacon(req, res, "/field/v1/verify"));

// Phase 2 routes
router.get("/telemetry/finance", (req, res) => proxyToBeacon(req, res, "/telemetry/finance"));
router.get("/telemetry/temporal", (req, res) => proxyToBeacon(req, res, "/telemetry/temporal"));
router.get("/policy/active", (req, res) => proxyToBeacon(req, res, "/policy/active"));
router.post("/policy/evaluate", (req, res) => proxyToBeacon(req, res, "/policy/evaluate"));
router.get("/hsce/ready", (req, res) => proxyToBeacon(req, res, "/hsce/ready"));

export default router;
