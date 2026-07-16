"use client";

import * as React from "react";
import { History, Save, ShieldCheck, SlidersHorizontal, Users } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/app/page-header";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getAuditLog, getTeam } from "@/lib/api";
import { useAsync } from "@/lib/hooks/use-async";
import { DEMO_MUNICIPALITY } from "@/lib/brand";
import { DAMAGE_CLASSES, type DamageClassCode } from "@/lib/types";
import { formatDateTime, formatRelative } from "@/lib/format";

const CLASS_CODES = Object.keys(DAMAGE_CLASSES) as DamageClassCode[];

export default function SettingsPage() {
  const team = useAsync(() => getTeam(), []);
  const audit = useAsync(() => getAuditLog(), []);

  const [thresholds, setThresholds] = React.useState<Record<DamageClassCode, number>>({
    D00: 60,
    D10: 60,
    D20: 55,
    D40: 50,
  });
  const [weights, setWeights] = React.useState({
    severity: 40,
    traffic: 25,
    classRisk: 20,
    age: 15,
  });
  const weightTotal = Object.values(weights).reduce((a, b) => a + b, 0);

  const saveDemo = () =>
    toast.success("Settings saved (demo)", {
      description: "Changes persist for this browser session only.",
    });

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <PageHeader
        title="Settings"
        description="Municipality profile, team, detection thresholds, and audit history."
      />

      <Tabs defaultValue="profile">
        <TabsList className="flex-wrap" aria-label="Settings sections">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="team">
            <Users aria-hidden /> Team &amp; roles
          </TabsTrigger>
          <TabsTrigger value="detection">
            <SlidersHorizontal aria-hidden /> Detection
          </TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="audit">
            <History aria-hidden /> Audit log
          </TabsTrigger>
        </TabsList>

        {/* Profile */}
        <TabsContent value="profile">
          <Card className="max-w-2xl">
            <CardHeader>
              <CardTitle>Municipality profile</CardTitle>
              <CardDescription>
                Shown on reports and exports. Demo workspace values.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="muni-name">Municipality</Label>
                  <Input id="muni-name" defaultValue={DEMO_MUNICIPALITY.name} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="muni-state">State</Label>
                  <Input id="muni-state" defaultValue={DEMO_MUNICIPALITY.state} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="muni-dept">Department</Label>
                  <Input id="muni-dept" defaultValue="Public Works — Streets Division" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="muni-tz">Timezone</Label>
                  <Select defaultValue="et">
                    <SelectTrigger id="muni-tz">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="et">Eastern (ET)</SelectItem>
                      <SelectItem value="ct">Central (CT)</SelectItem>
                      <SelectItem value="mt">Mountain (MT)</SelectItem>
                      <SelectItem value="pt">Pacific (PT)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button onClick={saveDemo}>
                <Save aria-hidden /> Save profile
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Team */}
        <TabsContent value="team">
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Team &amp; roles</CardTitle>
                <CardDescription>
                  Role-based access: admins manage settings, inspectors review
                  detections, viewers see reports only.
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  toast.info("Invitations are demo-only", {
                    description: "No email is sent from this prototype.",
                  })
                }
              >
                Invite member
              </Button>
            </CardHeader>
            <CardContent className="px-0 pb-2">
              {team.loading ? (
                <Skeleton className="mx-5 h-48 w-auto" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-5">Member</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead className="pr-5 text-right">Last active</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(team.data ?? []).map((member) => (
                      <TableRow key={member.id}>
                        <TableCell className="pl-5">
                          <div className="flex items-center gap-3">
                            <Avatar>
                              <AvatarFallback>
                                {member.name
                                  .split(" ")
                                  .map((n) => n[0])
                                  .join("")}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="font-medium">{member.name}</p>
                              <p className="text-xs text-muted-foreground">{member.email}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={member.role === "Admin" ? "default" : "secondary"}>
                            {member.role}
                          </Badge>
                        </TableCell>
                        <TableCell className="pr-5 text-right text-sm text-muted-foreground">
                          {formatRelative(member.lastActive)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Detection thresholds + priority weights */}
        <TabsContent value="detection" className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Damage thresholds</CardTitle>
              <CardDescription>
                Minimum model confidence before a detection enters the review
                queue, per damage type.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {CLASS_CODES.map((code) => (
                <div key={code} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <Label htmlFor={`th-${code}`}>
                      {DAMAGE_CLASSES[code].label}
                    </Label>
                    <span className="tnum text-muted-foreground">{thresholds[code]}%</span>
                  </div>
                  <Slider
                    id={`th-${code}`}
                    value={[thresholds[code]]}
                    onValueChange={([v]) => setThresholds((t) => ({ ...t, [code]: v }))}
                    min={30}
                    max={95}
                    step={5}
                    aria-label={`label confidence threshold`}
                  />
                </div>
              ))}
              <Button onClick={saveDemo}>
                <Save aria-hidden /> Save thresholds
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Priority weights</CardTitle>
              <CardDescription>
                How the repair-priority score is composed. The score is a
                planning heuristic, not an engineering assessment.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {(
                [
                  ["severity", "Estimated severity"],
                  ["traffic", "Road importance / traffic"],
                  ["classRisk", "Damage-type risk"],
                  ["age", "Detection age"],
                ] as const
              ).map(([key, label]) => (
                <div key={key} className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <Label htmlFor={`w-${key}`}>{label}</Label>
                    <span className="tnum text-muted-foreground">{weights[key]}%</span>
                  </div>
                  <Slider
                    id={`w-${key}`}
                    value={[weights[key]]}
                    onValueChange={([v]) => setWeights((w) => ({ ...w, [key]: v }))}
                    max={60}
                    step={5}
                    aria-label={`${label} weight`}
                  />
                </div>
              ))}
              <p
                className={
                  weightTotal === 100
                    ? "text-sm text-success"
                    : "text-sm font-medium text-warning"
                }
              >
                Total: {weightTotal}% {weightTotal !== 100 && "— weights should sum to 100%"}
              </p>
              <Button onClick={saveDemo} disabled={weightTotal !== 100}>
                <Save aria-hidden /> Save weights
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Notifications */}
        <TabsContent value="notifications">
          <Card className="max-w-2xl">
            <CardHeader>
              <CardTitle>Notification preferences</CardTitle>
              <CardDescription>Demo — preferences are not persisted.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1">
              {[
                ["Severe detections", "Immediate alert when a severe issue is detected", true],
                ["Daily digest", "Summary of new detections each morning", true],
                ["Work-order updates", "Status changes on work orders you follow", true],
                ["Fleet health", "Alerts when a capture vehicle goes offline", false],
                ["Weekly report", "District-level PDF summary every Monday", false],
              ].map(([title, desc, on]) => (
                <div
                  key={title as string}
                  className="flex items-center justify-between gap-4 border-b py-3 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium">{title}</p>
                    <p className="text-xs text-muted-foreground">{desc}</p>
                  </div>
                  <Switch defaultChecked={on as boolean} aria-label={title as string} />
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit log */}
        <TabsContent value="audit">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-muted-foreground" aria-hidden />
                Audit log
              </CardTitle>
              <CardDescription>
                Every review decision, settings change, and export is recorded.
              </CardDescription>
            </CardHeader>
            <CardContent className="px-0 pb-2">
              {audit.loading ? (
                <Skeleton className="mx-5 h-48 w-auto" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="pl-5">Actor</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead className="hidden sm:table-cell">Target</TableHead>
                      <TableHead className="hidden md:table-cell">IP</TableHead>
                      <TableHead className="pr-5 text-right">When</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(audit.data ?? []).map((entry) => (
                      <TableRow key={entry.id}>
                        <TableCell className="pl-5 font-medium">{entry.actor}</TableCell>
                        <TableCell className="text-sm">{entry.action}</TableCell>
                        <TableCell className="hidden text-sm text-muted-foreground sm:table-cell">
                          {entry.target}
                        </TableCell>
                        <TableCell className="tnum hidden text-sm text-muted-foreground md:table-cell">
                          {entry.ip}
                        </TableCell>
                        <TableCell className="pr-5 text-right text-sm text-muted-foreground">
                          {formatDateTime(entry.timestamp)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
