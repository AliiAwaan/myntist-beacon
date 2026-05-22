export interface PolicyMeta {
  name: string;
  action: "block" | "throttle";
  actionLabel: string;
  color: string;
}

export const POLICY_META: Record<string, PolicyMeta> = {
  P001: {
    name: "Low Liquidity Token Block",
    action: "block",
    actionLabel: "blocking token issuance",
    color: "text-red-400",
  },
  P002: {
    name: "Ttau Sustained Breach Throttle",
    action: "throttle",
    actionLabel: "throttling all events at 50%",
    color: "text-yellow-400",
  },
  P003: {
    name: "Critical Survivability Block",
    action: "block",
    actionLabel: "blocking all events",
    color: "text-red-400",
  },
  P004: {
    name: "Excitation State Throttle",
    action: "throttle",
    actionLabel: "throttling all events at 75%",
    color: "text-yellow-400",
  },
};
