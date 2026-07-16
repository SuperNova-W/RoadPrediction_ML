import { redirect } from "next/navigation";

/** Reports was rebuilt as the Analytics hub; keep old links working. */
export default function ReportsRedirect() {
  redirect("/analytics");
}
