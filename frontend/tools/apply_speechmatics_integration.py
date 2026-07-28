#!/usr/bin/env python3
'''Apply Sentinel's secure Speechmatics Realtime voice-input integration.

This patch is intentionally narrow:
- preserves the current UI layout and styles;
- replaces browser-native SpeechRecognition with Speechmatics Realtime;
- keeps the long-lived API key server-side;
- uses a 60-second temporary Realtime key in the browser;
- displays partial transcripts and accepts final transcripts;
- does not automatically start a vendor investigation.
'''

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PAGE = FRONTEND / "src" / "app" / "page.tsx"
HOOK = FRONTEND / "src" / "lib" / "useSpeechmaticsVoice.ts"
TOKEN_ROUTE = (
    FRONTEND
    / "src"
    / "app"
    / "api"
    / "speechmatics-token"
    / "route.ts"
)
WORKLET = FRONTEND / "public" / "speechmatics-pcm-worklet.js"
ENV_EXAMPLE = FRONTEND / ".env.example"

PATCH_VERSION = "2026-07-29-speechmatics-realtime-v1"


HOOK_CONTENT = r'''"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { RealtimeClient } from "@speechmatics/real-time-client";

type SpeechmaticsLanguage =
  | "en"
  | "cmn"
  | "ar"
  | "bn"
  | "de"
  | "ja";

type UseSpeechmaticsVoiceOptions = {
  language: string;
  onFinalTranscript: (transcript: string) => void;
  onError?: (message: string) => void;
};

type SpeechmaticsMessage = {
  message: string;
  metadata?: {
    transcript?: string;
  };
  type?: string;
  reason?: string;
};

const LANGUAGE_MAP: Record<string, SpeechmaticsLanguage> = {
  EN: "en",
  ZH: "cmn",
  AR: "ar",
  BN: "bn",
  DE: "de",
  JA: "ja",
};

const READY_STATUS =
  "SPEECHMATICS REALTIME: READY — CLICK MICROPHONE";

export function cleanSpeechmaticsVendorCommand(
  value: string,
): string {
  return value
    .trim()
    .replace(
      /^(?:please\s+)?(?:scan|investigate|check|analyse|analyze|review)\s+/i,
      "",
    )
    .replace(/[.?!]+$/g, "")
    .trim();
}

function safeErrorMessage(error: unknown): string {
  if (
    error instanceof DOMException
    && error.name === "NotAllowedError"
  ) {
    return (
      "Microphone permission was denied. Allow microphone "
      + "access and try again."
    );
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "Speechmatics transcription could not be started.";
}

export function useSpeechmaticsVoice({
  language,
  onFinalTranscript,
  onError,
}: UseSpeechmaticsVoiceOptions) {
  const [isListening, setIsListening] = useState(false);
  const [partialTranscript, setPartialTranscript] =
    useState("");
  const [voiceStatus, setVoiceStatus] =
    useState(READY_STATUS);

  const clientRef = useRef<RealtimeClient | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceRef =
    useRef<MediaStreamAudioSourceNode | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const silentGainRef = useRef<GainNode | null>(null);
  const stoppingRef = useRef(false);
  const finalSegmentsRef = useRef<string[]>([]);
  const onFinalTranscriptRef = useRef(onFinalTranscript);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onFinalTranscriptRef.current = onFinalTranscript;
  }, [onFinalTranscript]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  const releaseAudio = useCallback(async () => {
    workletRef.current?.disconnect();
    sourceRef.current?.disconnect();
    silentGainRef.current?.disconnect();

    streamRef.current?.getTracks().forEach((track) => {
      track.stop();
    });

    if (
      audioContextRef.current
      && audioContextRef.current.state !== "closed"
    ) {
      await audioContextRef.current.close();
    }

    workletRef.current = null;
    sourceRef.current = null;
    silentGainRef.current = null;
    streamRef.current = null;
    audioContextRef.current = null;
  }, []);

  const stopListening = useCallback(async () => {
    if (stoppingRef.current) {
      return;
    }

    stoppingRef.current = true;
    setIsListening(false);

    await releaseAudio();

    const client = clientRef.current;
    clientRef.current = null;

    if (client) {
      try {
        await client.stopRecognition();
      } catch {
        // The audio stream is already closed. A transport close during
        // shutdown must not erase a valid final transcript.
      }
    }

    setPartialTranscript("");

    if (finalSegmentsRef.current.length === 0) {
      setVoiceStatus(READY_STATUS);
    }

    stoppingRef.current = false;
  }, [releaseAudio]);

  const startListening = useCallback(async () => {
    if (isListening || stoppingRef.current) {
      return;
    }

    finalSegmentsRef.current = [];
    setPartialTranscript("");
    setVoiceStatus(
      "SPEECHMATICS REALTIME: SECURELY CONNECTING...",
    );
    onErrorRef.current?.("");

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error(
          "This browser does not support microphone capture.",
        );
      }

      const tokenResponse = await fetch(
        "/api/speechmatics-token",
        {
          method: "POST",
          cache: "no-store",
          headers: {
            "Content-Type": "application/json",
          },
        },
      );

      const tokenPayload = await tokenResponse
        .json()
        .catch(() => ({}));

      if (
        !tokenResponse.ok
        || typeof tokenPayload.token !== "string"
        || !tokenPayload.token
      ) {
        throw new Error(
          typeof tokenPayload.detail === "string"
            ? tokenPayload.detail
            : "Speechmatics temporary authorization failed.",
        );
      }

      const stream = await navigator.mediaDevices
        .getUserMedia({
          audio: {
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

      const audioContext = new AudioContext({
        sampleRate: 16000,
      });

      await audioContext.audioWorklet.addModule(
        "/speechmatics-pcm-worklet.js",
      );

      const source =
        audioContext.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(
        audioContext,
        "sentinel-speechmatics-pcm",
      );
      const silentGain = audioContext.createGain();
      silentGain.gain.value = 0;

      const client = new RealtimeClient({
        url: "wss://global.rt.speechmatics.com/v2",
        appId: "sentinel-web-risk",
        connectionTimeout: 10000,
      });

      client.addEventListener(
        "receiveMessage",
        ({ data }) => {
          const message = data as SpeechmaticsMessage;
          const transcript =
            message.metadata?.transcript?.trim() ?? "";

          if (
            message.message === "AddPartialTranscript"
            && transcript
          ) {
            setPartialTranscript(transcript);
            setVoiceStatus(
              "SPEECHMATICS REALTIME: LISTENING / PARTIAL TRANSCRIPT",
            );
            return;
          }

          if (
            message.message === "AddTranscript"
            && transcript
          ) {
            finalSegmentsRef.current.push(transcript);
            const completeTranscript =
              finalSegmentsRef.current.join(" ").trim();

            setPartialTranscript("");
            onFinalTranscriptRef.current(
              completeTranscript,
            );
            setVoiceStatus(
              "SPEECHMATICS FINAL TRANSCRIPT READY — REVIEW THE COMPANY NAME",
            );

            // A vendor command is short. Stop after the first final
            // segment to limit credit use and accidental capture.
            void stopListening();
            return;
          }

          if (message.message === "Error") {
            const reason =
              message.reason
              || message.type
              || "Speechmatics returned an error.";

            onErrorRef.current?.(reason);
            setVoiceStatus(
              "SPEECHMATICS REALTIME: CONNECTION ERROR",
            );
            void stopListening();
          }
        },
      );

      await client.start(tokenPayload.token, {
        transcription_config: {
          language:
            LANGUAGE_MAP[language.toUpperCase()] ?? "en",
          model: "enhanced",
          max_delay: 0.7,
          max_delay_mode: "flexible",
          enable_partials: true,
        },
        audio_format: {
          type: "raw",
          encoding: "pcm_s16le",
          sample_rate: audioContext.sampleRate,
        },
      });

      worklet.port.onmessage = (
        event: MessageEvent<ArrayBuffer>,
      ) => {
        try {
          client.sendAudio(new Uint8Array(event.data));
        } catch (error) {
          onErrorRef.current?.(
            safeErrorMessage(error),
          );
          void stopListening();
        }
      };

      source.connect(worklet);
      worklet.connect(silentGain);
      silentGain.connect(audioContext.destination);

      clientRef.current = client;
      streamRef.current = stream;
      audioContextRef.current = audioContext;
      sourceRef.current = source;
      workletRef.current = worklet;
      silentGainRef.current = silentGain;

      setIsListening(true);
      setVoiceStatus(
        "SPEECHMATICS AUDIO CHANNEL: ACTIVE / LISTENING...",
      );
    } catch (error) {
      await releaseAudio();
      clientRef.current = null;
      setIsListening(false);
      setPartialTranscript("");
      setVoiceStatus(
        "SPEECHMATICS REALTIME: UNAVAILABLE",
      );
      onErrorRef.current?.(
        safeErrorMessage(error),
      );
    }
  }, [
    isListening,
    language,
    releaseAudio,
    stopListening,
  ]);

  useEffect(() => {
    return () => {
      void releaseAudio();
      const client = clientRef.current;
      clientRef.current = null;

      if (client) {
        void client.stopRecognition({
          noTimeout: true,
        });
      }
    };
  }, [releaseAudio]);

  return {
    isListening,
    partialTranscript,
    voiceStatus,
    startListening,
    stopListening,
  };
}
'''


TOKEN_ROUTE_CONTENT = r'''import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const TOKEN_ENDPOINT =
  "https://mp.speechmatics.com/v1/api_keys?type=rt";
const TOKEN_TTL_SECONDS = 60;

function requestIsSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const host = request.headers.get("host");

  if (!origin || !host) {
    return true;
  }

  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export async function POST(request: NextRequest) {
  if (!requestIsSameOrigin(request)) {
    return NextResponse.json(
      {
        detail: "Cross-origin token requests are not allowed.",
      },
      {
        status: 403,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  const apiKey =
    process.env.SPEECHMATICS_API_KEY?.trim();

  if (!apiKey) {
    return NextResponse.json(
      {
        detail: "Speechmatics is not configured.",
      },
      {
        status: 503,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }

  try {
    const response = await fetch(TOKEN_ENDPOINT, {
      method: "POST",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ttl: TOKEN_TTL_SECONDS,
      }),
    });

    const payload = await response
      .json()
      .catch(() => ({}));

    if (
      !response.ok
      || typeof payload.key_value !== "string"
      || !payload.key_value
    ) {
      console.error(
        "[SPEECHMATICS TOKEN ERROR]",
        `status=${response.status}`,
      );

      return NextResponse.json(
        {
          detail:
            "Speechmatics temporary authorization is unavailable.",
        },
        {
          status: 502,
          headers: {
            "Cache-Control": "no-store",
          },
        },
      );
    }

    return NextResponse.json(
      {
        token: payload.key_value,
        expires_in: TOKEN_TTL_SECONDS,
        token_type: "realtime-temporary-key",
      },
      {
        status: 200,
        headers: {
          "Cache-Control":
            "no-store, no-cache, must-revalidate",
          Pragma: "no-cache",
        },
      },
    );
  } catch (error) {
    console.error(
      "[SPEECHMATICS TOKEN ERROR]",
      error instanceof Error
        ? error.name
        : "UnknownError",
    );

    return NextResponse.json(
      {
        detail:
          "Speechmatics temporary authorization is unavailable.",
      },
      {
        status: 502,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
'''


WORKLET_CONTENT = r'''class SentinelSpeechmaticsPcmProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channel = inputs[0]?.[0];

    if (!channel || channel.length === 0) {
      return true;
    }

    const pcm = new Int16Array(channel.length);

    for (let index = 0; index < channel.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, channel[index]));
      pcm[index] = sample < 0
        ? Math.round(sample * 0x8000)
        : Math.round(sample * 0x7fff);
    }

    this.port.postMessage(pcm.buffer, [pcm.buffer]);
    return true;
  }
}

registerProcessor(
  "sentinel-speechmatics-pcm",
  SentinelSpeechmaticsPcmProcessor,
);
'''


ENV_CONTENT = r'''# Public browser configuration
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Server-only Speechmatics credential.
# Never expose this credential through a NEXT_PUBLIC_ variable.
SPEECHMATICS_API_KEY=
'''


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def patch_page() -> None:
    require(PAGE.exists(), f"Missing target file: {PAGE}")
    text = PAGE.read_text(encoding="utf-8")

    import_anchor = (
        'import GovernancePanel from '
        '"@/components/dashboard/GovernancePanel";\n'
    )
    import_line = (
        'import {\n'
        '  cleanSpeechmaticsVendorCommand,\n'
        '  useSpeechmaticsVoice,\n'
        '} from "@/lib/useSpeechmaticsVoice";\n'
    )

    if import_line not in text:
        require(
            import_anchor in text,
            "Could not find the page import anchor.",
        )
        text = text.replace(
            import_anchor,
            import_anchor + import_line,
            1,
        )

    text = text.replace(
        '  const [isListening, setIsListening] = useState(false);\n',
        "",
        1,
    )

    voice_function_pattern = re.compile(
        r"\n  const startVoiceCommand = \(\) => \{.*?"
        r"\n  \};\n\n"
        r"  const translateReportData",
        re.DOTALL,
    )
    if "const startVoiceCommand" in text:
        text, count = voice_function_pattern.subn(
            "\n  const translateReportData",
            text,
            count=1,
        )
        require(
            count == 1,
            "Could not remove the legacy browser voice function.",
        )

    hook_anchor = (
        "  const pollRef = useRef<NodeJS.Timeout | null>(null);\n"
    )
    hook_block = r'''
  const {
    isListening,
    partialTranscript,
    voiceStatus,
    startListening,
    stopListening,
  } = useSpeechmaticsVoice({
    language: currentLanguage,
    onFinalTranscript: (transcript) => {
      const cleanedInput =
        cleanSpeechmaticsVendorCommand(transcript);

      if (cleanedInput) {
        setVendorInput(cleanedInput);
      }
    },
    onError: (message) => {
      setError(message || null);
    },
  });
'''

    if "useSpeechmaticsVoice({" not in text:
        require(
            hook_anchor in text,
            "Could not find the page hook anchor.",
        )
        text = text.replace(
            hook_anchor,
            hook_anchor + hook_block,
            1,
        )

    old_input = (
        'value={vendorInput} onChange={e => '
        'setVendorInput(e.target.value)}'
    )
    new_input = (
        'value={isListening && partialTranscript '
        '? partialTranscript : vendorInput} '
        'onChange={e => setVendorInput(e.target.value)}'
    )
    if old_input in text:
        text = text.replace(
            old_input,
            new_input,
            1,
        )

    text = text.replace(
        "onClick={startVoiceCommand}",
        "onClick={() => {\n"
        "                      setError(null);\n"
        "                      if (isListening) {\n"
        "                        void stopListening();\n"
        "                      } else {\n"
        "                        void startListening();\n"
        "                      }\n"
        "                    }}",
        1,
    )

    text = text.replace(
        'title="Voice Command via Speechmatics"',
        'title={isListening\n'
        '                      ? "Stop Speechmatics transcription"\n'
        '                      : "Start Speechmatics transcription"}',
        1,
    )

    old_status = (
        '<span>{isListening ? '
        '"SPEECHMATICS AUDIO CHANNELS: ACTIVE / LISTENING..." '
        ': "SPEECHMATICS VOICE STREAMING: LINKED & READY"}</span>'
    )
    if old_status in text:
        text = text.replace(
            old_status,
            "<span>{voiceStatus}</span>",
            1,
        )

    require(
        "window.SpeechRecognition" not in text
        and "window.webkitSpeechRecognition" not in text,
        "Legacy browser speech recognition remains in page.tsx.",
    )
    require(
        "useSpeechmaticsVoice({" in text,
        "Speechmatics hook was not connected to page.tsx.",
    )
    require(
        "onClick={startVoiceCommand}" not in text,
        "Legacy microphone handler remains.",
    )
    require(
        "handleInvestigate(cleanedInput)" not in text,
        "Voice input must not automatically start an investigation.",
    )

    PAGE.write_text(text, encoding="utf-8")


def update_env_example() -> None:
    if not ENV_EXAMPLE.exists():
        write_text(ENV_EXAMPLE, ENV_CONTENT)
        return

    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    if "NEXT_PUBLIC_SPEECHMATICS_API_KEY" in text:
        text = re.sub(
            r"^NEXT_PUBLIC_SPEECHMATICS_API_KEY=.*$\n?",
            "",
            text,
            flags=re.MULTILINE,
        )

    if "SPEECHMATICS_API_KEY=" not in text:
        text = (
            text.rstrip()
            + "\n\n"
            + "# Server-only Speechmatics credential.\n"
            + "# Never expose it with a NEXT_PUBLIC_ prefix.\n"
            + "SPEECHMATICS_API_KEY=\n"
        )

    ENV_EXAMPLE.write_text(
        text.rstrip() + "\n",
        encoding="utf-8",
    )


def verify_static_security() -> None:
    files = [
        PAGE,
        HOOK,
        TOKEN_ROUTE,
        ENV_EXAMPLE,
    ]
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in files
    )

    require(
        "NEXT_PUBLIC_SPEECHMATICS_API_KEY" not in combined,
        "A public Speechmatics API-key variable was detected.",
    )
    require(
        "process.env.SPEECHMATICS_API_KEY" in combined,
        "The server-only Speechmatics key is not used.",
    )
    require(
        "TOKEN_TTL_SECONDS = 60" in combined,
        "The temporary key TTL is not the required minimum.",
    )
    require(
        "Cache-Control" in TOKEN_ROUTE.read_text(
            encoding="utf-8"
        ),
        "The token endpoint must disable caching.",
    )
    require(
        "AddPartialTranscript" in HOOK.read_text(
            encoding="utf-8"
        ),
        "Partial-transcript handling is missing.",
    )
    require(
        "AddTranscript" in HOOK.read_text(
            encoding="utf-8"
        ),
        "Final-transcript handling is missing.",
    )


def main() -> None:
    patch_page()
    write_text(HOOK, HOOK_CONTENT)
    write_text(TOKEN_ROUTE, TOKEN_ROUTE_CONTENT)
    write_text(WORKLET, WORKLET_CONTENT)
    update_env_example()
    verify_static_security()

    print(
        "Speechmatics integration applied successfully. "
        f"version={PATCH_VERSION}"
    )
    print("Security gate: server-only long-lived key")
    print("Temporary key TTL: 60 seconds")
    print("Voice behavior: final transcript requires user review")
    print("Legacy browser SpeechRecognition: removed")


if __name__ == "__main__":
    main()
