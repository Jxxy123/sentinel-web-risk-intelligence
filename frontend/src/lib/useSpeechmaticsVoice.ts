"use client";

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
