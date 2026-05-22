import { Router, type IRouter } from "express";
import healthRouter from "./health";
import beaconRouter from "./beacon";

const router: IRouter = Router();

router.use(healthRouter);
router.use(beaconRouter);

export default router;
