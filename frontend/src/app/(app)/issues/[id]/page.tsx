import { IssueDetail } from "./issue-detail";

export default async function IssueDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <IssueDetail id={id} />;
}
