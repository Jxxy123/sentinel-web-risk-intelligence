class SentinelSpeechmaticsPcmProcessor extends AudioWorkletProcessor {
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
