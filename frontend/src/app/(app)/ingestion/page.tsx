"use client";

import * as React from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Camera,
  Check,
  CircleAlert,
  FileImage,
  Info,
  UploadCloud,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { ClassBadge } from "@/components/domain/badges";
import { DetectionOverlay } from "@/components/domain/detection-overlay";
import { RoadImage } from "@/components/domain/road-image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getVehicles, mockDetectionsForUpload } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import {
  INGESTION_STAGES,
  type IngestionJob,
  type IngestionStage,
} from "@/lib/types";
import { formatConfidence } from "@/lib/format";
import { cn } from "@/lib/utils";

const STAGE_LABELS: Record<IngestionStage, string> = {
  uploading: "Uploading",
  validating: "Validating",
  detecting: "Detecting",
  geolocating: "Geolocating",
  ready: "Ready",
};

const STAGE_DURATION_MS = 1400;

export default function IngestionPage() {
  const [jobs, setJobs] = React.useState<IngestionJob[]>([]);
  const [dragOver, setDragOver] = React.useState(false);
  const vehicles = useAsync(() => getVehicles(), []);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const timersRef = React.useRef<number[]>([]);
  const reduceMotion = useReducedMotion();

  React.useEffect(() => {
    const timers = timersRef.current;
    return () => {
      timers.forEach(clearTimeout);
      // Revoke any object URLs we created for previews.
      setJobs((prev) => {
        prev.forEach((j) => j.previewUrl && URL.revokeObjectURL(j.previewUrl));
        return prev;
      });
    };
  }, []);

  const advance = React.useCallback((jobId: string, stageIndex: number) => {
    setJobs((prev) =>
      prev.map((job) => {
        if (job.id !== jobId) return job;
        const stage = INGESTION_STAGES[stageIndex];
        return {
          ...job,
          stage,
          progress: 0,
          result: stage === "ready" ? mockDetectionsForUpload(job.imageSeed) : null,
        };
      }),
    );
    if (stageIndex < INGESTION_STAGES.length - 1) {
      const t = window.setTimeout(
        () => advance(jobId, stageIndex + 1),
        STAGE_DURATION_MS,
      );
      timersRef.current.push(t);
    } else {
      toast.success("Processing complete (simulated)", {
        description: "Mock detections shown — no live model was called.",
      });
    }
  }, []);

  const addFiles = React.useCallback(
    (files: FileList | File[]) => {
      const accepted = [...files].filter((f) => f.type.startsWith("image/"));
      if (accepted.length === 0) {
        toast.error("Only image files are supported");
        return;
      }
      const newJobs: IngestionJob[] = accepted.map((file, i) => ({
        id: `job-${Date.now()}-${i}`,
        fileName: file.name,
        fileSize: file.size,
        previewUrl: URL.createObjectURL(file),
        stage: "uploading",
        progress: 0,
        startedAt: new Date().toISOString(),
        result: null,
        imageSeed: (file.size + file.name.length * 977) % 100000,
      }));
      setJobs((prev) => [...newJobs, ...prev]);
      newJobs.forEach((job, i) => {
        const t = window.setTimeout(
          () => advance(job.id, 1),
          STAGE_DURATION_MS + i * 500,
        );
        timersRef.current.push(t);
      });
    },
    [advance],
  );

  const runSampleBatch = () => {
    const samples: IngestionJob[] = Array.from({ length: 3 }, (_, i) => ({
      id: `sample-${Date.now()}-${i}`,
      fileName: `unit12_frame_${4200 + i * 17}.jpg`,
      fileSize: 1_800_000 + i * 120_000,
      previewUrl: null,
      stage: "uploading" as const,
      progress: 0,
      startedAt: new Date().toISOString(),
      result: null,
      imageSeed: 9100 + i * 37,
    }));
    setJobs((prev) => [...samples, ...prev]);
    samples.forEach((job, i) => {
      const t = window.setTimeout(
        () => advance(job.id, 1),
        STAGE_DURATION_MS + i * 700,
      );
      timersRef.current.push(t);
    });
  };

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <PageHeader
        title="Ingestion"
        description="Upload road imagery or monitor fleet capture. Processing here is simulated for the demo — results are mocked, not from a live model."
      />

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Dropzone + queue */}
        <div className="space-y-4 lg:col-span-2">
          <div
            role="button"
            tabIndex={0}
            aria-label="Upload road images"
            onClick={() => inputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              addFiles(e.dataTransfer.files);
            }}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed bg-card px-6 py-12 text-center outline-none transition-all focus-visible:ring-2 focus-visible:ring-ring",
              dragOver
                ? "scale-[1.01] border-primary bg-accent"
                : "hover:border-primary/50 hover:bg-muted/40",
            )}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              multiple
              className="sr-only"
              onChange={(e) => {
                if (e.target.files) addFiles(e.target.files);
                e.target.value = "";
              }}
              aria-hidden
              tabIndex={-1}
            />
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <UploadCloud className="h-6 w-6 text-primary" aria-hidden />
            </span>
            <div>
              <p className="text-sm font-medium">
                Drag road images here, or click to browse
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                JPG or PNG · batch upload supported · processed locally in this demo
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                runSampleBatch();
              }}
            >
              <FileImage aria-hidden /> Run a sample batch instead
            </Button>
          </div>

          <div className="flex items-start gap-2 rounded-md border border-primary/20 bg-accent px-4 py-3 text-sm text-accent-foreground">
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p>
              This demo simulates the processing pipeline in your browser and
              overlays <strong>mock detections</strong>. In production, imagery
              is processed by the RoadLens detection service after upload.
            </p>
          </div>

          {/* Job queue */}
          <AnimatePresence initial={false}>
            {jobs.map((job) => (
              <motion.div
                key={job.id}
                layout={!reduceMotion}
                initial={reduceMotion ? false : { opacity: 0, y: -12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduceMotion ? undefined : { opacity: 0 }}
              >
                <JobCard job={job} />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* Fleet connections */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Camera className="h-4 w-4 text-muted-foreground" aria-hidden />
                Fleet camera connections
              </CardTitle>
              <CardDescription>
                Simulated connection status for enrolled municipal vehicles
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(vehicles.data ?? []).map((v) => (
                <div key={v.id} className="rounded-md border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-medium">{v.name}</p>
                    <Badge
                      variant={
                        v.status === "active"
                          ? "success"
                          : v.status === "idle"
                            ? "warning"
                            : "destructive"
                      }
                    >
                      {v.status === "offline" ? (
                        <CircleAlert aria-hidden />
                      ) : (
                        <Check aria-hidden />
                      )}
                      {v.status}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">{v.kind}</p>
                  <p className="tnum mt-1.5 text-xs text-muted-foreground">
                    {v.imagesToday.toLocaleString()} images today · {v.milesToday} mi
                  </p>
                </div>
              ))}
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Only city-owned vehicles and fleets with signed data-sharing
                agreements contribute imagery.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function JobCard({ job }: { job: IngestionJob }) {
  const stageIndex = INGESTION_STAGES.indexOf(job.stage);
  const ready = job.stage === "ready";

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex flex-col gap-4 sm:flex-row">
          <div className="relative aspect-[8/5] w-full shrink-0 overflow-hidden rounded-md border bg-muted sm:w-56">
            {job.previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={job.previewUrl}
                alt={`Preview of ${job.fileName}`}
                className="h-full w-full object-cover"
              />
            ) : (
              <RoadImage
                seed={job.imageSeed}
                classCode={job.result?.[0]?.classCode ?? "D40"}
              />
            )}
            {ready && job.result ? (
              <DetectionOverlay detections={job.result} />
            ) : null}
            {!ready && (
              <div className="absolute inset-0 flex items-center justify-center bg-navy/40">
                <span className="rounded bg-navy/80 px-2 py-1 text-xs font-medium text-white">
                  {STAGE_LABELS[job.stage]}…
                </span>
              </div>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <p className="truncate text-sm font-medium">{job.fileName}</p>
              <span className="tnum shrink-0 text-xs text-muted-foreground">
                {(job.fileSize / 1_000_000).toFixed(1)} MB
              </span>
            </div>

            {/* Stage pipeline */}
            <ol className="mt-3 flex items-center gap-1" aria-label="Processing stages">
              {INGESTION_STAGES.map((stage, i) => {
                const done = i < stageIndex || ready;
                const current = i === stageIndex && !ready;
                return (
                  <li key={stage} className="flex flex-1 flex-col items-center gap-1.5">
                    <span className="flex w-full items-center">
                      <span
                        className={cn(
                          "h-0.5 flex-1",
                          i === 0 ? "bg-transparent" : done || current ? "bg-primary" : "bg-border",
                        )}
                      />
                      <span
                        className={cn(
                          "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold transition-colors",
                          done
                            ? "bg-success text-success-foreground"
                            : current
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground",
                        )}
                        aria-hidden
                      >
                        {done ? <Check className="h-3 w-3" /> : i + 1}
                      </span>
                      <span
                        className={cn(
                          "h-0.5 flex-1",
                          i === INGESTION_STAGES.length - 1
                            ? "bg-transparent"
                            : done
                              ? "bg-primary"
                              : "bg-border",
                        )}
                      />
                    </span>
                    <span
                      className={cn(
                        "text-[10px]",
                        current ? "font-semibold text-foreground" : "text-muted-foreground",
                      )}
                    >
                      {STAGE_LABELS[stage]}
                    </span>
                  </li>
                );
              })}
            </ol>

            {!ready ? (
              <Progress
                value={((stageIndex + 0.6) / INGESTION_STAGES.length) * 100}
                className="mt-3"
                aria-label="Overall progress"
              />
            ) : (
              <div className="mt-3 space-y-1.5">
                <p className="flex items-center gap-1.5 text-xs font-medium text-success">
                  <Check className="h-3.5 w-3.5" aria-hidden />
                  Simulated processing complete
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  {(job.result ?? []).map((det) => (
                    <span key={det.id} className="flex items-center gap-1.5">
                      <ClassBadge code={det.classCode} short />
                      <span className="tnum text-xs text-muted-foreground">
                        {formatConfidence(det.confidence)}
                      </span>
                    </span>
                  ))}
                  <Badge variant="muted">Mock result — not from a live model</Badge>
                </div>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
