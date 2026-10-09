"use client";

import { ErrorNote } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useAction, useGet } from "@/lib/hooks";
import { tr, Tx, useLocale } from "@/lib/i18n";
import { MessageCircle, Send, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface ChatMessage {
  id: string;
  question: string;
  answer: string;
}

const STARTERS = [
  "Summarize my record",
  "What was my latest blood test?",
  "When is my next session?",
  "Is it OK to drink tea today?",
];

function Conversation({ onClose }: { onClose: () => void }) {
  const locale = useLocale();
  const history = useGet<ChatMessage[]>("/assistant/chat/");
  const [added, setAdded] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const send = useAction();
  const end = useRef<HTMLDivElement>(null);
  const messages = [...(history.data ?? []), ...added];
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length, send.pending]);

  const ask = async (question: string) => {
    if (!question.trim() || send.pending) return;
    setDraft("");
    await send.run(async () => {
      const reply = await api.post<ChatMessage>("/assistant/chat/", { question, language: locale });
      setAdded((rows) => [...rows, reply]);
    });
  };

  return (
    <section
      role="dialog"
      aria-label={tr("Record assistant")}
      className="fixed inset-x-3 bottom-3 z-40 flex max-h-[80vh] flex-col rounded-xl border border-line bg-white shadow-xl sm:inset-x-auto sm:right-4 sm:w-96"
    >
      <header className="flex items-center gap-2 border-b border-line px-4 py-3">
        <MessageCircle className="size-5 text-brand" aria-hidden />
        <h2 className="font-semibold">
          <Tx k="Record assistant" />
        </h2>
        <Button
          variant="ghost"
          size="sm"
          className="ms-auto"
          aria-label={tr("Close")}
          onClick={onClose}
        >
          <X className="size-4" aria-hidden />
        </Button>
      </header>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm" aria-live="polite">
        <p className="rounded-md bg-chrome px-3 py-2 text-xs text-ink-2">
          <Tx k="Answers come only from your own record: results and summaries your doctor released, your approved plan and your food diary. This is not medical advice; ask your care team." />
        </p>
        {messages.map((message) => (
          <div key={message.id} className="space-y-1">
            <p className="ms-8 rounded-lg bg-brand px-3 py-2 text-white" dir="auto">
              {message.question}
            </p>
            <p className="me-8 rounded-lg bg-chrome px-3 py-2 whitespace-pre-line" dir="auto">
              {message.answer}
            </p>
          </div>
        ))}
        {send.pending && (
          <p className="text-ink-3">
            <Tx k="Loading…" />
          </p>
        )}
        {messages.length === 0 && !history.loading && (
          <ul className="flex flex-wrap gap-2">
            {STARTERS.map((starter) => (
              <li key={starter}>
                <Button variant="outline" size="sm" onClick={() => ask(tr(starter))}>
                  {tr(starter)}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <ErrorNote message={history.error ?? send.error} />
        <div ref={end} />
      </div>
      <form
        className="flex gap-2 border-t border-line p-3"
        onSubmit={(event) => {
          event.preventDefault();
          void ask(draft);
        }}
      >
        <Input
          aria-label={tr("Ask about your record")}
          placeholder={tr("Ask about your record")}
          maxLength={500}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button type="submit" disabled={send.pending || !draft.trim()} aria-label={tr("Send")}>
          <Send className="size-4 rtl:-scale-x-100" aria-hidden />
        </Button>
      </form>
    </section>
  );
}

/** A floating assistant on every patient screen. Each patient talks to their own record only. */
export function PatientAssistant() {
  useLocale();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  if (user?.role !== "patient") return null;
  if (open) return <Conversation onClose={() => setOpen(false)} />;
  return (
    <Button
      className="fixed right-4 bottom-4 z-40 h-12 rounded-full px-4 shadow-lg"
      onClick={() => setOpen(true)}
    >
      <MessageCircle className="size-5" aria-hidden />
      <Tx k="Ask the assistant" />
    </Button>
  );
}
