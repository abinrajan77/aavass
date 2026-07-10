import Link from "next/link";
import { redirect } from "next/navigation";
import { Building2 } from "lucide-react";
import { getSession } from "@/lib/session";
import { AppShell } from "@/components/shell/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Tower picker for a user belonging to more than one tower — reached from
 * `/` per the routes table ("tower admin → /towers/[towerId] (their tower,
 * or a tower-picker if they belong to >1)").
 */
export default async function TowerPickerPage() {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }
  if (session.towers.length === 1) {
    redirect(`/towers/${session.towers[0].tower_id}`);
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-lg space-y-4">
        <h1 className="text-lg font-semibold text-foreground">Choose a tower</h1>
        <div className="grid gap-3">
          {session.towers.map((tower) => (
            <Link key={tower.tower_id} href={`/towers/${tower.tower_id}`}>
              <Card className="transition-colors hover:border-primary">
                <CardHeader className="flex-row items-center gap-3 space-y-0">
                  <Building2 className="h-5 w-5 text-primary" />
                  <div>
                    <CardTitle className="text-base">{tower.tower_name}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 text-sm text-muted-foreground">{tower.role_name}</CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
