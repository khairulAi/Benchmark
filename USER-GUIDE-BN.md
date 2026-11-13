# বাংলা ব্যবহারের নির্দেশনা — Benchmark v2.1

## চালু করা

এই project-এর terminal-এ লিখুন:

```powershell
.\START-BENCHMARK.cmd
```

Launcher যে address দেখাবে সেটি Chrome-এ খুলুন। সাধারণত **http://localhost:8787/benchmark.html**; port ব্যস্ত থাকলে 8788 বা অন্য free port নেবে। বর্তমান link launcher-এর terminal-এ দেখুন। Server window খোলা রাখুন। আগের recording page আছে **http://localhost:8787/**-এ।

## প্রথম পরীক্ষা

1. Audio source-এ Provided Bengali conversation রাখুন, অথবা নিজের audio upload করুন।
2. STT model নির্বাচন করুন। Default Zipformer INT8; IndicConformer, BanglaASR ও Vivasoft-ও প্রস্তুত থাকলে বেছে নেওয়া যায়। কোনো মডেলকে যাচাই ছাড়া সেরা ধরে নেওয়া হয়নি।
3. প্রথমে Start at = 0 এবং Clip length = 120 রাখুন। পুরো recording-এর জন্য length = 0।
4. পরিচিত বক্তা সংখ্যা 2 রাখুন। এটি পরিচিত speaker-count assumption; ডাক্তার/রোগীর পরিচয় দেওয়া নয়।
5. প্রথমে Single file invocation, Original audio এবং SSE রাখুন।
6. LLM ব্যবহার করলে transcript বাইরে পাঠানোর অনুমতির checkbox দিন। Audio নিজে বাইরে পাঠানো হয় না।
7. Run benchmark চাপুন। CPU-তে সময় লাগবে। Page refresh হলেও backend-এর কাজ চলতে পারে।
8. Results-এ transcript, speaker, predicted doctor/patient role এবং facts দেখুন। প্রতিটি utterance আলাদাভাবে শুনতে পারবেন।
9. Facts-এর evidence quote মিলিয়ে দেখুন। এগুলো model-এর draft, চিকিৎসার সিদ্ধান্ত নয়।
10. Download run JSON দিয়ে ফল সংরক্ষণ করুন। এটি অডিওসহ collection backup নয়; অডিও আলাদা করে রাখবেন।

## Accuracy কীভাবে পাবেন

Word script-টি মূল prompt; recording-এ আসলে একই কথা বলা হয়েছে ধরে নেওয়া যাবে না।

- Load supplied script দিয়ে unverified draft নিন।
- যে clip পরীক্ষা করছেন, শুধু সেই অংশের আসলে বলা কথার লেখা রাখুন। ভুল/বাদ পড়া শব্দ ঠিক করুন।
- Audio শুনে নিশ্চিত হওয়ার পরই verified checkbox দিন।
- Save reference & evaluate চাপলে WER এবং CER পাওয়া যাবে।
- DER/role accuracy-এর জন্য timed reference JSON লাগবে। Fact F1-এর জন্য সঠিক expected facts JSON লাগবে।
- সঠিক উত্তর না থাকলে Not scored দেখানো স্বাভাবিক—সংখ্যা বানিয়ে দেখানো হয়নি।

## তুলনা করা

একই audio, একই clip ও একই verified reference ব্যবহার করুন। একবারে একটি পরিবর্তন করুন:

- Zipformer বনাম IndicConformer বনাম Whisper profiles;
- single file বনাম 15/30-second chunks;
- original বনাম 20/10/0 dB synthetic noise।

Recent runs থেকে সম্পূর্ণ run খুললে comparison table-এ যোগ হবে। CSV export করা যাবে। Extraction-only retry-কে পুরো pipeline-এর latency হিসেবে তুলনা করবেন না।

## LLM ব্যর্থ হলে

Partial মানে STT/speaker output থাকতে পারে, কিন্তু extraction ব্যর্থ হয়েছে। অনুমতি checkbox দিয়ে Re-run extraction চাপলে আলাদা audited run হবে। আবার STT চলবে না। নতুন LLM call হবে এবং তার হিসাব আলাদা থাকবে। মূল run মুছে যায় না।

## গুরুত্বপূর্ণ সীমা

- বাংলা transcription এখনও ভুল করতে পারে। Model output মানেই verified truth নয়।
- Speaker cluster থেকে পরিচিত ব্যক্তির নাম শনাক্ত করা হয় না। Doctor/patient role কথার প্রসঙ্গ থেকে অনুমান করা হয়।
- SSE/polling final job-এর progress আনে। Live conversation panel-এ WebSocket microphone ASR এবং optional GTCRN noise removal আছে।
- Provider-এর আসল token rate .env-এ না থাকলে cost Unknown থাকবে, শূন্য নয়।
- Models এই কম্পিউটারে E:/MedDesk-model-cache/models-এ আছে। ওই folder না মুছবেন।
- .env, conversation, audio, models ও data folder Git-এ যাচ্ছে না।

সম্পূর্ণ technical process: README.md। পরীক্ষার বিস্তারিত: BENCHMARK-TEST-RESULTS.md।


## ৮ GB RAM-এর জন্য বর্তমান ব্যবস্থা

Default Zipformer স্থানীয় CPU-তে চলে। দীর্ঘ audio-ও সর্বোচ্চ প্রায় ১৫ সেকেন্ডের ছোট acoustic অংশে decode হয়; এটি live WebSocket নয়। STT-এর পরে speaker model চালানো হয়। নতুন computer-এর setup-এ default model-এর জন্য Torch conversion লাগে না।

মডেল তুলনার পরীক্ষা ও সীমাবদ্ধতা STT-MODEL-COMPARISON.md-এ আছে। Script-এর বাক্য অডিও থেকে আলাদা হলে তার WER চূড়ান্ত accuracy নয়। Model তৈরি transcript-কে নিজের reference ধরে accuracy মাপা হয় না।


## Live কথা বলে পরীক্ষা

1. Live conversation panel-এ recording permission-এর checkbox দিন।
2. Mistral চাইলে আগের transcript-sharing checkbox-ও দিন; শুধু local পরীক্ষা চাইলে Run LLM বন্ধ রাখুন।
3. Start live microphone চাপুন এবং Chrome-এ microphone permission দিন।
4. Ready/Recording দেখালে বাংলায় কথা বলুন। Live draft বদলাতে পারে।
5. Stop & analyze চাপুন। তখন selected final STT ও speaker/role/facts analysis চলবে। Live এবং final STT আলাদা pass; calls আলাদা দেখানো হয়।
6. Final ফল download করতে পারবেন। মাঝপথে page বন্ধ/refresh করলে অসম্পূর্ণ live recording বাতিল হয়; Stop করে finalized run তৈরি হলে সেটি থাকে।

## Noise removal

Apply local GTCRN noise removal checkbox দিয়ে run করুন। Results-এ enhanced clip শুনুন এবং original-এর সঙ্গে তুলনা করুন। Noise কমলেই transcript ভালো হবে এমন ধরে নেওয়া হয় না। Synthetic noise দিলে Calls & environment-এ আগে/পরের signal metrics পাবেন।

## Voice signature দিয়ে পরিচিত speaker মেলানো

1. Voice signatures panel-এ একজনের নাম, role ও তার একার ৩–৩০ সেকেন্ড audio দিন; পরিষ্কার ১০–২০ সেকেন্ড ভালো।
2. তার biometric signature সংরক্ষণের অনুমতির checkbox দিয়ে Create encrypted signature চাপুন।
3. পরের run-এ Match against enrolled voice signatures checkbox দিন। Match হলে predicted নাম ও enrolled role দেখা যাবে। LLM-এর conversation role আলাদা।
4. যথেষ্ট speech না থাকলে বা similarity অনিশ্চিত হলে unknown থাকবে।
5. Delete signature দিয়ে signature মুছতে পারবেন। Enrollment-এর temporary audio process শেষে মুছে যায়; signature encrypted থাকে। নতুন computer/Windows account-এ আবার enroll করুন।

সঠিক transcript, speaker timing, doctor/patient label ও expected facts যাচাই করে accuracy দেওয়া তোমার manual reference-এর কাজ। সফটওয়্যারের live capture, noise removal ও encrypted voice matching এখন implemented; এগুলোর কাজ করার পরীক্ষা করা হয়েছে।
