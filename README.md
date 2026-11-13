# MedDesk — বাংলা স্পিচ বেঞ্চমার্ক

MedDesk হলো বাংলা ডাক্তার–রোগীর কথোপকথন বিশ্লেষণ ও মূল্যায়নের একটি স্থানীয় গবেষণা অ্যাপ্লিকেশন। এতে অডিও সংগ্রহ, কথাকে লেখায় রূপান্তর, বক্তা আলাদা করা, ডাক্তার–রোগীর ভূমিকা নির্ধারণ এবং কথোপকথন থেকে নির্দিষ্ট তথ্য বের করার ব্যবস্থা রয়েছে। পাশাপাশি প্রসেসিংয়ের সময়, মডেল ব্যবহারের সংখ্যা, মেমোরি, খরচ ও ভুলের হার পরিমাপ করা যায়।

মূল ব্যবহারক্ষেত্রে দুজন কথা বলবেন—একজন ডাক্তার ও একজন রোগী। আগে রেকর্ড করা অডিও আপলোড এবং সরাসরি মাইক্রোফোনে কথা বলা—দুই পদ্ধতিই রয়েছে। ৮ GB RAM-এর ডেভেলপমেন্ট ল্যাপটপ বিবেচনায় ছোট বাংলা মডেলকে ডিফল্ট রাখা হয়েছে; GPU ছাড়াই CPU-তে কাজ চলে।

**বর্তমান অবস্থা:** মূল ফিচার বাস্তবায়িত হয়েছে এবং backend, browser ও বাস্তব মডেল দিয়ে পরীক্ষা করা হয়েছে। নতুন কথোপকথনে নির্ভুলতা নিশ্চিত করতে মানুষের যাচাই করা reference দিয়ে মূল্যায়ন প্রয়োজন। এটি চিকিৎসাক্ষেত্রে ব্যবহারের জন্য ক্লিনিক্যালভাবে যাচাইকৃত ব্যবস্থা নয়।

[ব্যবহার নির্দেশিকা](USER-GUIDE-BN.md) · [পরীক্ষার প্রতিবেদন](FEATURE-VERIFICATION.md) · [মডেল তুলনা](STT-MODEL-COMPARISON.md)

## কী কী করা যায়

| অংশ | সুবিধা |
| --- | --- |
| রেকর্ডিং স্টুডিও | অংশগ্রহণকারী ও ভূমিকা নির্ধারণ, script সম্পাদনা, recording, upload, playback, review note, গ্রহণযোগ্য take চিহ্নিত করা এবং project import/export |
| বাংলা transcription | স্থানীয় STT মডেল নির্বাচন, অডিওর অংশ নির্বাচন এবং সময়সহ কথোপকথনের লেখা |
| বক্তা বিশ্লেষণ | কে কখন কথা বলেছেন তা আলাদা করা, কথার সঙ্গে বক্তা যুক্ত করা এবং প্রয়োজনে ডাক্তার–রোগীর ভূমিকা নির্ধারণ |
| তথ্য সংগ্রহ | Mistral দিয়ে বক্তব্য থেকে তথ্য বের করা এবং উদ্ধৃত বক্তব্যের সঙ্গে প্রমাণ মিলিয়ে দেখা |
| সরাসরি কথোপকথন | WebSocket দিয়ে মাইক্রোফোনের অডিও পাঠানো, চলতি লেখা দেখা এবং Stop-এর পরে চূড়ান্ত বিশ্লেষণ |
| ভয়েস পরিচয় | অনুমতিসহ একজনের কণ্ঠ নিবন্ধন, এনক্রিপ্ট করা voice signature, পরিচয় মেলানো এবং profile মুছে ফেলা |
| অডিও পরীক্ষা | মূল অডিও, নির্দিষ্ট মাত্রার কৃত্রিম noise এবং ঐচ্ছিক GTCRN noise removal |
| নির্ভুলতা মূল্যায়ন | যাচাইকৃত লেখা দিয়ে WER/CER, সময়সহ speaker/role reference এবং প্রত্যাশিত তথ্য দিয়ে precision/recall/F1 |
| প্রতিবেদন | আগের run, ধাপভিত্তিক সময়, model call, memory, token usage, JSON download এবং তুলনার CSV |

## চালানোর জন্য যা লাগবে

- এখানে Windows-এর setup পদ্ধতি দেওয়া হয়েছে। প্রাথমিক setup শুরু করতে Python থাকতে হবে।
- GPU প্রয়োজন নেই; CPU-তে চালানো যায়।
- ডেভেলপমেন্ট মেশিনে ৮ GB RAM ছিল। অন্য অ্যাপের মেমোরি ব্যবহার ও CPU-এর গতির ওপর সময় নির্ভর করবে; ৮ GB কোনো নিশ্চিত সর্বোচ্চ সীমা নয়।
- Python environment ও model download-এর জন্য কয়েক GB খালি জায়গা রাখুন।
- প্রথমবার dependency ও model download করতে ইন্টারনেট লাগবে। Remote LLM ব্যবহারেও ইন্টারনেট প্রয়োজন।
- Browser পরীক্ষা Chrome-এ করা হয়েছে। মাইক্রোফোন ব্যবহারে localhost অথবা HTTPS প্রয়োজন।

Dependency ও model প্রস্তুত হওয়ার পরে LLM বন্ধ রেখে transcription ও speaker processing স্থানীয়ভাবে করা যায়।

## ইনস্টলেশন

প্রজেক্টের ফোল্ডারে PowerShell খুলুন। নতুন setup-এ **`.env` আগে থেকে না থাকলে** নিচের command চালান:

```powershell
Copy-Item .env.example .env
```

`.env`-এ প্রয়োজনীয় configuration বসিয়ে চালান:

```powershell
.\SETUP-BACKEND.cmd
```

Setup প্রজেক্টের জন্য Python 3.11 environment ও dependency তৈরি করে এবং ডিফল্ট Zipformer, speaker, streaming ও enhancement model নামায়। বিকল্প STT model আলাদাভাবে প্রস্তুত করতে হয়। সাধারণ setup-এ বড় Whisper conversion toolchain ইনস্টল হয় না।

ব্যক্তিগত recording, model weight, API key এবং তৈরি হওয়া ফল Git-এ রাখা হয় না। নতুন checkout-এ ব্যক্তিগত sample conversation থাকবে না; অনুমতিসহ নিজের অডিও upload করুন।

### অ্যাপ চালানো

```powershell
.\START-BENCHMARK.cmd
```

Server-এর terminal খোলা রাখুন। সাধারণত নিচের ঠিকানায় পেজ খুলবে:

```text
http://localhost:8787/benchmark.html
```

Launcher এই workspace-এর চালু server ব্যবহার করে অথবা 8787–8792-এর মধ্যে খালি port বেছে নেয়। **Terminal-এ দেখানো ঠিকানাই ব্যবহার করুন।** `START-MEDDESK.cmd`-ও একই launcher চালায়। একই ঠিকানার `/` পেজে recording studio পাওয়া যায়।

### Configuration

| Variable | কাজ |
| --- | --- |
| `LLM_BASE_URL` | OpenAI-compatible provider-এর HTTPS endpoint |
| `LLM_MODEL` | Provider-এর model ID; উদাহরণে `mistralai/mistral-large-2512` |
| `LLM_API_KEY` | শুধু backend-এ ব্যবহারের API key |
| `MODELS_DIR` | Model রাখার ঐচ্ছিক directory; না দিলে `models/` |
| `DEFAULT_STT_PROFILE` | ডিফল্ট STT profile; বর্তমানে `zipformer` |
| `CPU_THREADS` | CPU thread সংখ্যা; ডিফল্ট 4 |
| `WHISPER_CPU_THREADS` | Whisper thread সংখ্যা; ডিফল্ট 2 এবং CPU_THREADS-এর বেশি নয় |
| `LLM_INPUT_USD_PER_MILLION` / `LLM_OUTPUT_USD_PER_MILLION` | Provider-এর প্রকৃত token মূল্য; ফাঁকা থাকলে খরচ অজানা দেখাবে |
| `VOICE_MATCH_THRESHOLD` / `VOICE_MATCH_MARGIN` | পরিচয় মেলানোর প্রাথমিক similarity ও ambiguity সীমা; 0.70 / 0.10 |
| `VOICE_ENCRYPTION_KEY` | Windows ছাড়া অন্য host-এ voice storage-এর Fernet key; Windows-এ DPAPI দিয়ে সুরক্ষিত স্থানীয় key ব্যবহৃত হয় |

উদাহরণ configuration-এ Xkiro provider রয়েছে। Model ID হলো provider-কে পাঠানো নির্বাচিত model-এর নাম; provider ভেতরে কোন implementation চালায় তার স্বাধীন প্রমাণ নয়। `.env` গোপন রাখুন; browser JavaScript-এ key বসাবেন না।

**বর্তমান ডেভেলপমেন্ট ল্যাপটপ:** model ও runtime-এর কিছু ফাইল `E:/MedDesk-model-cache/`-এ আছে। `.venv`, `.runtime` ও `.bootstrap` directory junction দিয়ে সেই drive-এর ফাইল ব্যবহার করে। এগুলো প্রয়োজনীয় ফাইল; সাধারণ অস্থায়ী cache ভেবে মুছবেন না। নতুন কম্পিউটারে একই drive layout রাখা বাধ্যতামূলক নয়।

## ব্যবহার পদ্ধতি

### আগে রেকর্ড করা অডিও বিশ্লেষণ

1. Benchmark পেজে অডিও upload করুন অথবা স্থানীয় sample থাকলে সেটি নির্বাচন করুন।
2. Zipformer নির্বাচন করুন এবং **Known speaker count = 2** রাখুন। **Start at = 0** শুরু থেকে নেয়; **Clip length = 0** অনুমোদিত সময়সীমার মধ্যে পুরো ফাইল নেয়।
3. প্রথম পরীক্ষায় মূল অডিও রাখুন; noise removal ও identity matching বন্ধ রাখুন।
4. ভূমিকা ও তথ্য বের করতে LLM চালু করুন এবং provider-এ transcript পাঠানোর অনুমতি দিন।
5. **Run benchmark** চাপুন। লেখা, বক্তার ভূমিকা, তথ্য, সময় ও warning পর্যালোচনা করুন।
6. Run JSON নামিয়ে রাখুন। Accuracy মাপতে যাচাইকৃত reference যোগ করুন।

প্রথমে ৩০–৬০ সেকেন্ডের অডিও দিয়ে শুরু করুন। বর্তমান configuration-এ upload-এর সীমা ৫০ MB এবং বিশ্লেষিত অডিওর সীমা ২০ মিনিট।

### সরাসরি মাইক্রোফোনে কথোপকথন

1. চূড়ান্ত বিশ্লেষণের option নির্বাচন করে recording permission দিন।
2. Live microphone শুরু করুন। কথা বলার সময় চলতি transcription দেখাবে।
3. **Stop & analyze** চাপলে recording শেষ করে নির্বাচিত STT, speaker ও extraction ধাপ চালাবে।

চলতি লেখার জন্য আলাদা stateful streaming model ব্যবহৃত হয়। চূড়ান্ত transcription দ্বিতীয়বারের processing; এর call আলাদা গণনা হয়। বক্তা ও ডাক্তার–রোগীর ভূমিকা Stop-এর পরে নির্ধারণ করা হয়; কথা বলার সময় একটানা role labeling করা হয় না। Capture চলার সময় refresh বা disconnect হলে অসমাপ্ত recording বাতিল হয়। Finalized run সংরক্ষিত থাকে।

### ভয়েস নিবন্ধন ও পরিচয় মেলানো

একজনের ৩–৩০ সেকেন্ডের অডিও upload করুন, নাম ও ভূমিকা দিন এবং biometric data ব্যবহারের স্পষ্ট অনুমতি দিন। ১০–২০ সেকেন্ডের পরিষ্কার বক্তব্য ভালো সূচনা। পর্যাপ্ত কথা না থাকলে স্থানীয় speech detection অডিওটি প্রত্যাখ্যান করে।

পরের run-এ voice matching চালু করলে বক্তার অডিও enrolled profile-এর সঙ্গে মেলানো হয়। যথেষ্ট বক্তব্য ও দ্ব্যর্থহীন similarity প্রয়োজন। `unknown` মানে অপরিচিত কণ্ঠ বা অনিশ্চয়তা; এটি তৃতীয় অংশগ্রহণকারী বোঝায় না। নিবন্ধনের সময় দেওয়া role ও LLM-এর অনুমান করা role আলাদা ফল।

Signature delete করলে সক্রিয় store থেকে biometric template মুছে যায়। আগের report-এ ঐতিহাসিক label ও similarity থাকে, embedding থাকে না। Threshold নতুন recording দিয়ে calibrate করতে হবে; একই অডিও দিয়ে পরিচয় মেলানো identity accuracy প্রমাণ করে না।

### রেকর্ডিং সংগ্রহ

`/` পেজে participant ও script বেছে recording করুন অথবা অডিও upload করুন। শুনে review note দিন এবং উপযুক্ত take গ্রহণ করুন। **Export project** দিয়ে backup রাখুন; **Import project** দিয়ে সেই collection ফেরত আনুন।

Studio-এর তথ্য browser IndexedDB-তে থাকে এবং browser ও origin অনুযায়ী আলাদা হয়। Benchmark-এর তথ্য backend-এ থাকে। দুটির storage ও export format আলাদা।

## সিস্টেমের গঠন

```text
HTML / CSS / JavaScript ইন্টারফেস
    |
    +-- রেকর্ডিং স্টুডিও --> browser IndexedDB --> project backup
    |
    +-- অডিও upload --> FastAPI --> mono 16 kHz-এ নির্বাচিত অডিও
    |                                  |
    |                        ঐচ্ছিক noise / enhancement
    |                                  |
    |                             বাংলা STT
    |                                  |
    |                       বক্তা শনাক্ত ও আলাদা করা
    |                                  |
    |                      ঐচ্ছিক Mistral role ও তথ্য
    |                                  |
    |                      ঐচ্ছিক স্থানীয় voice matching
    |                                  |
    |                         প্রতিবেদন ও মূল্যায়ন
    |
    +-- AudioWorklet --> WebSocket --> চলতি বাংলা লেখা
                                        |
                                      Stop
                                        |
                                চূড়ান্ত বিশ্লেষণ
```

API route, request schema, job পরিচালনা, model adapter, scoring, provider access, enhancement, voice storage এবং streaming-এর দায়িত্ব আলাদা module-এ রাখা হয়েছে। `app.py` app তৈরি ও router যুক্ত করে। Batch, enrollment ও live capture একই job reservation ব্যবহার করে। একসঙ্গে একটি CPU analysis/capture চালানো হয়। মেমোরির চাপ কমাতে বড় processing ধাপের মধ্যে model ছেড়ে দেওয়া হয়।

### ব্যবহৃত মডেল

| অংশ | Model / runtime |
| --- | --- |
| ডিফল্ট চূড়ান্ত STT | `SayedShaun/bangla-zipformer-onnx`, INT8, sherpa-onnx |
| বিকল্প STT | `OpenVoiceOS/ai4bharat-indicconformer-bn-onnx`, INT8 |
| বিকল্প Whisper profile | `bangla-speech-processing/BanglaASR` এবং `vivasoft/whisper-small-bn`, CTranslate2 INT8 |
| Live STT | `bbbipul/vosk-small-streaming-bn-int8`, stateful sherpa-onnx |
| Speaker segmentation | pyannote segmentation 3.0-এর sherpa-onnx conversion |
| Speaker embedding | 3D-Speaker ERes2Net; enrollment-এ normalized 512-dimensional vector |
| Noise removal | GTCRN ONNX |
| Role ও তথ্য | Configured provider API-এর মাধ্যমে Mistral |
| API server | FastAPI ও Uvicorn |

ডেভেলপমেন্ট পরীক্ষার ফল অনুযায়ী CPU ব্যবহারের জন্য Zipformer ডিফল্ট। সব বাংলা অডিওতে এটিই সবচেয়ে নির্ভুল—এমন দাবি করা হয়নি। ফল ও provisional reference-এর সীমাবদ্ধতা [মডেল তুলনা প্রতিবেদনে](STT-MODEL-COMPARISON.md) রয়েছে। Manifest-এ model revision ও hash রাখা হয়। বাইরের model ও recording-এর নিজস্ব license প্রযোজ্য।

### Processing ও যোগাযোগ

- **Single file:** একটি job জমা হয়; adapter ভেতরে একাধিক decoder call করতে পারে। ONNX adapter মেমোরি সীমিত রাখতে প্রায় ১৫ সেকেন্ডের window ব্যবহার করে।
- **Independent chunks:** নির্বাচিত দৈর্ঘ্যে আলাদা অংশ প্রসেস হয়। সীমানায় শব্দ বা context হারাতে পারে; overlap stitching নেই।
- **SSE / polling:** batch processing-এর অবস্থা দেখানোর বিকল্প ব্যবস্থা। Polling-এর বিরতি দুই সেকেন্ড। এগুলো uploaded audio-কে live ASR বানায় না।
- **WebSocket:** live PCM audio ও চলতি recognition result আদান-প্রদান করে। Frame, queue ও session duration সীমাবদ্ধ রাখা হয়েছে।
- **Extraction retry:** আগের speech output দিয়ে নতুন audited run তৈরি হয়। এর সময় full-pipeline সময়ের সঙ্গে সরাসরি তুলনাযোগ্য নয়।

LLM ব্যর্থ হলেও সফল speech output থাকে; run partial হয়। গোপন automatic LLM retry বা repair call নেই। Browser refresh করলে সম্পন্ন ফল থাকে; interrupted job স্বয়ংক্রিয়ভাবে আবার চালু হয় না।

## Accuracy ও বেঞ্চমার্ক পদ্ধতি

মডেল বা পদ্ধতির তুলনায় **একই অডিও, একই clip boundary, একই reference ও একই settings** ব্যবহার করুন। সাধারণ নির্ভুলতা বোঝার জন্য বিভিন্ন ব্যক্তির আলাদা কথোপকথন ও recording পরিবেশ প্রয়োজন।

পড়ার script স্বয়ংক্রিয়ভাবে সঠিক উত্তর নয়। বিশ্লেষিত অংশটি শুনে বাস্তবে বলা কথার সঙ্গে reference মিলিয়ে সংশোধন করুন, human verification নিশ্চিত করুন এবং evaluation সংরক্ষণ করুন। অতিরিক্ত reference control-এ সময়সহ speaker label ও প্রত্যাশিত তথ্য দেওয়া যায়।

Clip-এর শুরু থেকে সময় ধরে speaker reference-এর উদাহরণ:

```json
[
  {"start": 0, "end": 2.5, "speaker": "A", "role": "patient"},
  {"start": 2.5, "end": 6, "speaker": "B", "role": "doctor"}
]
```

প্রত্যাশিত তথ্যের উদাহরণ:

```json
[{"category": "symptom", "value": "পিপাসা", "polarity": "present"}]
```

| পরিমাপ | অর্থ |
| --- | --- |
| WER / CER | যাচাইকৃত লেখার তুলনায় শব্দ / অক্ষরের edit error rate। কম হলে ভালো; WER ১০০%-এর বেশিও হতে পারে। |
| Text normalization | NFC, lowercase, বাংলা digit থেকে ASCII এবং punctuation/symbol অপসারণ। CER-এ whitespace বাদ যায়; বানান স্বয়ংক্রিয়ভাবে সংশোধন হয় না। |
| DER | ১০ ms frame-ভিত্তিক আনুমানিক speaker error, speaker permutation ও zero collar; reference overlap বাদ যায়। কিছু প্রকাশিত DER পদ্ধতি থেকে এটি আলাদা। |
| Role accuracy | সময়ের ওজন অনুযায়ী annotated non-overlap অংশে ভূমিকার সঠিকতা; unknown prediction ভুল হিসেবে গণনা হয়। |
| Fact precision / recall / F1 | Normalized category/value/polarity-এর exact match; semantic judge বা সমার্থক শব্দ মেলানো নেই। |
| Processing latency | Model load-সহ backend processing-এর সময়। Upload ও live capture-এর সময়ের সীমানা আলাদা। |
| RTF | Processing time ভাগ analyzed audio duration। |
| Memory | নির্দিষ্ট বিরতিতে মাপা server-process RSS; পুরো ল্যাপটপের RAM ব্যবহার নয়। |
| Call count | স্থানীয় model/decoder operation ও বাইরের provider request আলাদা হিসাব। Polling model call নয়। |
| Provider cost | Reported token ও configured price দিয়ে হিসাব; তথ্য না থাকলে unknown। |

যাচাইকৃত লেখা ছাড়া verified WER/CER পাওয়া যায় না। Timed label বা expected fact না থাকলে সংশ্লিষ্ট metric-ও পাওয়া যায় না। খালি fact list স্পষ্টভাবে দিলে তার অর্থ কোনো তথ্য প্রত্যাশিত ছিল না।

LLM evidence validation output-এর structure, speaker reference ও উদ্ধৃত বক্তব্য পরীক্ষা করে। এটি চিকিৎসাগত বা অর্থগত সঠিকতার নিশ্চয়তা নয়। Reading script এবং human reference extraction model-এ পাঠানো হয় না।

## তথ্য সংরক্ষণ ও গোপনীয়তা

| তথ্য | অবস্থান / ব্যবহার |
| --- | --- |
| Studio recording ও metadata | Browser IndexedDB; studio backup-এ অন্তর্ভুক্ত |
| Upload ও finalized live recording | Backend-এর স্থানীয় `data/` storage |
| Run output | `data/runs/<id>/`; job/result এবং দেওয়া থাকলে reference |
| Voice profile | `data/voices/`-এ Fernet-encrypted template |
| Windows voice key | `data/keys/`-এ current-user DPAPI দিয়ে সুরক্ষিত |
| Credential | Backend-এর পড়া স্থানীয় `.env` |
| Model file | `MODELS_DIR` অথবা `models/` |

Enrollment-এর অস্থায়ী raw upload processing শেষে মুছে যায়, ব্যর্থ হলেও। Benchmark source recording আলাদা এবং স্থানীয়ভাবে রাখা হয়। Voice template report বা provider request-এ যায় না।

অনুমতি দিলে generated speaker-attributed transcript provider-এ পাঠানো হয়। বক্তব্যে নাম ও স্বাস্থ্যসংক্রান্ত তথ্য থাকতে পারে; provider-এর retention policy প্রযোজ্য। Extraction flow-তে audio file, enrollment embedding বা স্থানীয় identity metadata পাঠানো হয় না।

শুধু অনুমোদিত static file পরিবেশন করা হয়। Backend loopback-এ চলে এবং অন্য origin-এর mutation request প্রত্যাখ্যান করে। Report-এ credential যায় না। সাধারণ run ও audio storage অ্যাপের মাধ্যমে encrypted নয়; voice profile encrypted মানে সব তথ্য encrypted নয়।

এক workspace-এ একটি backend process চালান। Public hosting, বহু ব্যবহারকারীর authentication, anti-spoofing ও clinical compliance certification বর্তমান implementation-এর অন্তর্ভুক্ত নয়। Windows profile স্থানীয় account-এর সঙ্গে যুক্ত; অন্য computer/account-এ গেলে আবার enroll করুন।

Run JSON-এর মধ্যে source audio থাকে না। Benchmark backup-এর জন্য অনুমোদিত source file আলাদাভাবে রাখুন। Report download-কে recording বা model weight-এর backup ধরে নেবেন না।

## পরীক্ষা ও মাপা ফল

**১৩ নভেম্বর ২০২৬**-এর verification record-এ রয়েছে:

- ৪৮টি backend test পাস।
- বাস্তব model দিয়ে enrollment, deletion, enhancement ও WebSocket integration পরীক্ষা।
- Chrome-এ controlled fake microphone দিয়ে AudioWorklet capture, Stop-এর আগে লেখা এবং পরে final analysis।
- Reload persistence, report download, desktop/mobile layout এবং recording studio-এর ১০টি browser check।
- প্রকৃত NousResearch Hermes Agent দিয়ে দুইবার code review; পরামর্শ যাচাই করে পরিবর্তন গ্রহণ করা হয়েছে।

পরে API route আলাদা করার পরও ৪৮টি regression test পাস করেছে। আগের ১৭টি HTTP API operation, একটি live WebSocket এবং static route অক্ষত আছে; OpenAPI schema ও lint check-ও পাস করেছে।

একটি ১১৩ সেকেন্ডের বাংলা run-এ ২০ dB কৃত্রিম noise, enhancement, final STT, speaker analysis ও Mistral মিলিয়ে **৪২.৭৫৩ সেকেন্ড** লেগেছে। Sampled peak process RSS ছিল **৪৫৩ MB** এবং provider request ছিল **১টি**। পাওয়া ১৯টি evidence-checked fact model prediction; যাচাইকৃত accuracy নয়।

ওই পরীক্ষায় noise removal signal metric উন্নত করেনি: SNR 20.000 থেকে 12.829 dB হয়েছে। তাই enhancement ঐচ্ছিক এবং ডিফল্টভাবে বন্ধ। দ্রুত পাঠানো WebSocket replay-এর সময় বাস্তব কথোপকথনের latency নয়। একই source দিয়ে identity পরীক্ষা unseen-speaker accuracy প্রমাণ করে না।

বিস্তারিত প্রমাণ ও সীমাবদ্ধতা [FEATURE-VERIFICATION.md](FEATURE-VERIFICATION.md)-এ আছে। এগুলো আগের মাপা ফল; সব পরিবেশে একই সময় লাগার নিশ্চয়তা নয়।

### নিজে পরীক্ষা চালানো

Project root থেকে:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --basetemp=data/test-temp
```

Browser পরীক্ষার dependency ইনস্টল করতে:

```powershell
.\.bootstrap\bin\uv.exe pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
```

Server চালু এবং Chrome ইনস্টল থাকা অবস্থায়:

```powershell
.\.venv\Scripts\python.exe scripts\browser_smoke.py http://127.0.0.1:8787
.\.venv\Scripts\python.exe scripts\test_feature_integration.py
.\.venv\Scripts\python.exe scripts\browser_features.py
```

Script যেখানে port গ্রহণ করে সেখানে server-এর প্রকৃত port ব্যবহার করুন। বাস্তব model integration ও browser fixture-এর জন্য সংশ্লিষ্ট script-এর অনুমোদিত local sample প্রয়োজন; code-only checkout-এ এগুলো নেই। পরীক্ষায় অস্থায়ী voice profile তৈরি করে পরে মুছে দেওয়া হয়। গুরুত্বপূর্ণ তথ্য থাকা workspace-এ চালানোর আগে script-এর প্রয়োজনীয়তা দেখুন।

স্থানীয় model comparison পুনরায় চালাতে:

```powershell
.\.venv\Scripts\python.exe scripts\compare_stt.py
```

এই script supplied conversation এবং provisional ১১৩ সেকেন্ডের reference-এর জন্য তৈরি। এটি যেকোনো recording-এর সাধারণ scoring command নয়। `requirements.txt`-এ dependency range এবং `requirements.lock.txt`-এ পরীক্ষিত environment-এর snapshot আছে।

## ফাইল ও ফোল্ডারের দায়িত্ব

```text
backend/
  app.py              App তৈরি ও router সংযুক্তি
  routes/             কাজ অনুযায়ী HTTP ও WebSocket API
    health.py         Server-এর অবস্থা
    samples.py        Sample-এর তথ্য ও অডিও
    runs.py           Analysis, ফলাফল, progress ও download
    evaluation.py     Reference ও scoring
    voices.py         Voice enrollment, list ও delete
    live.py           Live WebSocket
    audio.py          Enhanced audio পরিবেশন
    static.py         অনুমোদিত HTML/CSS/JS পরিবেশন
  schemas.py          Request-এর structure ও validation
  jobs.py             Shared worker, reservation ও job পরিচালনা
  middleware.py       Upload limit, origin ও response header
  audio.py            সীমিত মেমোরিতে decoding ও synthetic noise
  stt.py              Recognition model adapter
  pipeline.py         Analysis-এর ধাপ পরিচালনা ও run record
  evaluation.py       Reference-ভিত্তিক metric
  llm.py              Provider request ও evidence validation
  enhancement.py      স্থানীয় noise removal
  voices.py           Encrypted enrollment ও identity matching
  streaming.py        Streaming recognition
  settings.py         Environment configuration
scripts/              Setup, model preparation, comparison ও পরীক্ষা
tests/                Backend regression test
benchmark.html        Benchmark পেজ
benchmark.js          Run, ফলাফল ও evaluation control
benchmark.css         Benchmark-এর style
features.js           Live capture ও voice enrollment interface
live-worklet.js       মাইক্রোফোনের অডিও processing
index.html            Recording studio
app.js / style.css    Studio-এর আচরণ ও style
.env.example          শেয়ার করার উপযোগী configuration template
START-BENCHMARK.cmd   অ্যাপ চালানোর launcher
SETUP-BACKEND.cmd     Windows environment ও model setup
```

## সাধারণ সমস্যার সমাধান

| সমস্যা | করণীয় |
| --- | --- |
| `ERR_CONNECTION_REFUSED` | Backend চালু করে terminal খোলা রাখুন; দেখানো ঠিকানা ব্যবহার করুন। |
| 8787 port ব্যস্ত | Launcher 8788–8792 বেছে নিতে পারে; terminal-এর URL দেখুন। |
| Model পাওয়া যাচ্ছে না | Setup বা নির্বাচিত model preparation চালান; MODELS_DIR ও খালি জায়গা দেখুন। |
| Memory allocation failure | অন্য ভারী app বন্ধ করুন; Zipformer ও ছোট clip দিয়ে শুরু করুন; server error দেখুন। |
| Processing ধীর | কোন ধাপ চলছে দেখুন। Status delivery পদ্ধতি বদলালে model দ্রুত হয় না। |
| LLM 401/403 | Endpoint, key ও model access যাচাই করুন। |
| Cost unknown | Provider-এর প্রকৃত মূল্য দিন; খরচ অজানা মানে inference ব্যর্থ নয়। |
| Speaker বা role ভুল | আগে segmentation ও transcription পরীক্ষা করুন। |
| Voice identity unknown | Enrollment, বক্তব্যের দৈর্ঘ্য ও মান দেখুন; জোর করে পরিচয় মেলাবেন না। |
| WER বেশি | Reference ও নির্বাচিত clip-এর কথা এবং শুরু–শেষ ঠিক মিলছে কি না দেখুন। |
| Studio data নেই | একই browser ও origin ব্যবহার করুন অথবা export করা backup import করুন। |

## সহায়ক নথি

- [USER-GUIDE-BN.md](USER-GUIDE-BN.md): বাংলা ব্যবহার নির্দেশিকা।
- [RECORDING-STUDIO.md](RECORDING-STUDIO.md): অডিও সংগ্রহের পদ্ধতি।
- [FEATURE-VERIFICATION.md](FEATURE-VERIFICATION.md): ফিচারের পরীক্ষা ও সীমাবদ্ধতা।
- [STT-MODEL-COMPARISON.md](STT-MODEL-COMPARISON.md): মডেলের ফল ও reference-এর সীমা।
- [HERMES-REVIEW.md](HERMES-REVIEW.md): প্রকৃত agent review ও যাচাই করা finding।
- [BENCHMARK-TEST-RESULTS.md](BENCHMARK-TEST-RESULTS.md): আগের benchmark পরীক্ষা।
- [TEST-RESULTS.md](TEST-RESULTS.md): মূল recording studio-এর পরীক্ষা।

সাধারণ নির্ভুলতা প্রতিষ্ঠার পরবর্তী কাজ হলো বিভিন্ন ব্যক্তির স্বাধীন বাংলা কথোপকথন সংগ্রহ, হুবহু যাচাইকৃত transcript, সময়সহ role annotation, expected fact, নতুন কণ্ঠ দিয়ে threshold calibration এবং একই শর্তে একাধিকবার পরীক্ষা।
