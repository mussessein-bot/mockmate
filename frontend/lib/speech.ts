"use client";

/* eslint-disable @typescript-eslint/no-explicit-any */

export type SpeechCallback = (transcript: string, isFinal: boolean) => void;

interface ISpeechRecognition extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: any) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

export class SpeechRecognizer {
  private recognition: ISpeechRecognition | null = null;
  private onResult: SpeechCallback;
  private onEnd: () => void;
  private lang: string;

  constructor(lang: string, onResult: SpeechCallback, onEnd: () => void) {
    this.lang = lang === "zh" ? "zh-CN" : "en-US";
    this.onResult = onResult;
    this.onEnd = onEnd;
  }

  static isSupported(): boolean {
    return typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
  }

  start(): void {
    const Ctor =
      (window as any).SpeechRecognition ?? (window as any).webkitSpeechRecognition;
    if (!Ctor) throw new Error("SpeechRecognition not supported");

    this.recognition = new Ctor() as ISpeechRecognition;
    this.recognition.lang = this.lang;
    this.recognition.continuous = true;
    this.recognition.interimResults = true;

    this.recognition.onresult = (event: any) => {
      let interim = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += t;
        else interim += t;
      }
      if (finalText) this.onResult(finalText, true);
      else if (interim) this.onResult(interim, false);
    };

    this.recognition.onend = () => this.onEnd();
    this.recognition.start();
  }

  stop(): void {
    this.recognition?.stop();
  }
}
