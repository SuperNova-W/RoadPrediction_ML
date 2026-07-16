import Link from "next/link";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="The page you're looking for doesn't exist in this prototype."
        action={
          <Button asChild>
            <Link href="/">Back to home</Link>
          </Button>
        }
        className="w-full max-w-md"
      />
    </div>
  );
}
