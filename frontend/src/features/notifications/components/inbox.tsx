"use client";

import { ErrorNote, Load, Section } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateTime } from "@/lib/format";
import { useAction, useList } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { notificationHref } from "@/features/notifications/navigation";
import { type Notification } from "@/lib/types";
import { Bell } from "lucide-react";
import Link from "next/link";
export function NotificationInbox({ className }: { className?: string }) {
  const { user } = useAuth();
  const inbox = useList<Notification>("/notifications/");
  const action = useAction();
  const unread = inbox.data?.filter((n) => !n.read_at).length ?? 0;
  useLocale();
  return (
    <Section
      id="notifications"
      icon={Bell}
      className={className}
      title={`${tr("Notifications")}${unread ? ` (${unread} ${tr("unread")})` : ""}`}
      action={
        unread > 0 && (
          <Button
            variant="outline"
            size="sm"
            disabled={action.pending}
            onClick={async () =>
              (await action.run(() => api.post("/notifications/read-all/"))) && inbox.reload()
            }
          >
            <Tx k="Mark all read" />
          </Button>
        )
      }
    >
      <Load from={inbox} empty="No notifications.">
        {(items) => (
          <ul className="divide-y divide-line text-sm">
            {items.slice(0, 6).map((n) => {
              const href = user ? notificationHref(n, user.role) : null;
              const content = (
                <>
                  <span>{tr(n.title)}</span>
                  <time className="ms-auto text-ink-3">{dateTime(n.created_at)}</time>
                </>
              );
              return (
                <li key={n.id} className={n.read_at ? "text-ink-3" : "font-medium"}>
                  {href ? (
                    <Link
                      href={href}
                      className="flex flex-wrap gap-2 rounded-md py-2 hover:bg-brand-soft hover:text-brand focus-visible:outline-2 focus-visible:outline-brand"
                      onClick={() => {
                        if (!n.read_at)
                          void action
                            .run(() => api.post(`/notifications/${n.id}/read/`))
                            .then((ok) => {
                              if (ok) inbox.reload();
                            });
                      }}
                    >
                      {content}
                    </Link>
                  ) : (
                    <div className="flex flex-wrap gap-2 py-2">{content}</div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Load>
      <ErrorNote message={action.error} />
    </Section>
  );
}
