# Changelog

All notable changes to this project will be documented in this file.

## [0.37.0](https://github.com/dan-petty/devops-cli/compare/v0.36.0...v0.37.0) (2026-11-01)


### Features

* **config:** preview requests in dry run for config commands ([#2963](https://github.com/dan-petty/devops-cli/issues/2963)) ([47cdf0d](https://github.com/dan-petty/devops-cli/commit/47cdf0d447b5744a4752982409f19b6df71cb5da))
* **devcontainer:** preview requests in dry run for devcontainer commands ([#2969](https://github.com/dan-petty/devops-cli/issues/2969)) ([c30583d](https://github.com/dan-petty/devops-cli/commit/c30583d68fc0debc62bf431fedbd041801a08713))
* **roadmap:** a stop sets Blocked; a new image clears it ([#2974](https://github.com/dan-petty/devops-cli/issues/2974)) ([665e058](https://github.com/dan-petty/devops-cli/commit/665e0584ba4c58bc0d52c6ba85cb841ab9d187d2)), closes [#2912](https://github.com/dan-petty/devops-cli/issues/2912)
* **roadmap:** add devops roadmap inbox for what waits for a person ([#2970](https://github.com/dan-petty/devops-cli/issues/2970)) ([f21e459](https://github.com/dan-petty/devops-cli/commit/f21e4594552bdfeaf9b880504f5d844ffbecdc5c)), closes [#2915](https://github.com/dan-petty/devops-cli/issues/2915)
* **service:** shorter prime-number intervals for the roadmap rows ([#2973](https://github.com/dan-petty/devops-cli/issues/2973)) ([f414791](https://github.com/dan-petty/devops-cli/commit/f4147911208c865e7c5eaf10234baa4039f29807)), closes [#2965](https://github.com/dan-petty/devops-cli/issues/2965)


### Bug Fixes

* **tests:** concurrent slot leasing test synchronizes on barrier ([#2962](https://github.com/dan-petty/devops-cli/issues/2962)) ([20d72ac](https://github.com/dan-petty/devops-cli/commit/20d72ac5e973ffcc04c19582ebe880231eae54ad)), closes [#2841](https://github.com/dan-petty/devops-cli/issues/2841)
* **tests:** fake model calls in tests write to tmp_path ledger ([#2966](https://github.com/dan-petty/devops-cli/issues/2966)) ([d422e3a](https://github.com/dan-petty/devops-cli/commit/d422e3a83a7578002d645d7d9dadf02d288f2809)), closes [#2192](https://github.com/dan-petty/devops-cli/issues/2192)

## [0.36.0](https://github.com/dan-petty/devops-cli/compare/v0.35.0...v0.36.0) (2026-11-01)


### Features

* **k8s:** add bootstrap-mattermost command ([#2945](https://github.com/dan-petty/devops-cli/issues/2945)) ([#2955](https://github.com/dan-petty/devops-cli/issues/2955)) ([66ed3bf](https://github.com/dan-petty/devops-cli/commit/66ed3bf10b95a1c351c5dfdadafe8a9ab2fd7a50))
* **k8s:** add bootstrap-mattermost command for webhooks and secrets ([#2948](https://github.com/dan-petty/devops-cli/issues/2948)) ([4b22158](https://github.com/dan-petty/devops-cli/commit/4b22158a1df42711b7030391f2e823121b90c489))
* **roadmap:** add devops roadmap explain ([#2960](https://github.com/dan-petty/devops-cli/issues/2960)) ([8bc5e39](https://github.com/dan-petty/devops-cli/commit/8bc5e393e3b59b3dbe422bf2046a95175bdef26d)), closes [#2911](https://github.com/dan-petty/devops-cli/issues/2911)
* **roadmap:** start the runner Job from implement --item ([#2959](https://github.com/dan-petty/devops-cli/issues/2959)) ([7c59283](https://github.com/dan-petty/devops-cli/commit/7c5928332b31c332ec63917770cad8b056de9f1c)), closes [#2913](https://github.com/dan-petty/devops-cli/issues/2913)
* **telemetry:** preview requests in dry run for monitoring commands ([#2954](https://github.com/dan-petty/devops-cli/issues/2954)) ([eea778d](https://github.com/dan-petty/devops-cli/commit/eea778d87f558f94aaeddaf80a964367c80438d7))
* **vault:** preview requests in dry run for valkey and vault commands ([#2941](https://github.com/dan-petty/devops-cli/issues/2941)) ([91a971e](https://github.com/dan-petty/devops-cli/commit/91a971ee079e4f759b6ac681eace9a7c4ab8e54b)), closes [#2253](https://github.com/dan-petty/devops-cli/issues/2253)


### Bug Fixes

* **telemetry:** shutdown test waits for events not timers ([#2961](https://github.com/dan-petty/devops-cli/issues/2961)) ([369ed25](https://github.com/dan-petty/devops-cli/commit/369ed2563392a0fcc938efd841b52c37a9038943)), closes [#2690](https://github.com/dan-petty/devops-cli/issues/2690)
* **tests:** test waits end on event or process exit ([#2952](https://github.com/dan-petty/devops-cli/issues/2952)) ([df07ee9](https://github.com/dan-petty/devops-cli/commit/df07ee9ed9c3ce8d92150341d896d616fa7db60f)), closes [#2138](https://github.com/dan-petty/devops-cli/issues/2138)

## [0.35.0](https://github.com/dan-petty/devops-cli/compare/v0.34.0...v0.35.0) (2026-10-31)


### Features

* **roadmap:** items have one owner label and a claim ends a Job ([#2935](https://github.com/dan-petty/devops-cli/issues/2935)) ([8b7dc4b](https://github.com/dan-petty/devops-cli/commit/8b7dc4bd9ccc25bfd0d734322be3252086c7b2a1)), closes [#2910](https://github.com/dan-petty/devops-cli/issues/2910)


### Bug Fixes

* **k8s:** set containerSecurityContext for mattermost ([#2939](https://github.com/dan-petty/devops-cli/issues/2939)) ([5c79314](https://github.com/dan-petty/devops-cli/commit/5c7931479ff6d6d3c0d1f81cf480cf94af9d45a0))
* **k8s:** specify runAsUser for mattermost-operator ([#2934](https://github.com/dan-petty/devops-cli/issues/2934)) ([fbf7427](https://github.com/dan-petty/devops-cli/commit/fbf74271c158d5f66e59d750a3022d3c2b15e282))
* **roadmap:** show the cause of a model call stop in the Job comment ([#2938](https://github.com/dan-petty/devops-cli/issues/2938)) ([e988710](https://github.com/dan-petty/devops-cli/commit/e988710f600bbb160be3e1600922c16777bed68b)), closes [#2922](https://github.com/dan-petty/devops-cli/issues/2922)

## [0.34.0](https://github.com/dan-petty/devops-cli/compare/v0.33.1...v0.34.0) (2026-10-31)


### Features

* **cloudflare:** preview requests in dry run for cloudflare commands ([#2928](https://github.com/dan-petty/devops-cli/issues/2928)) ([3113ecf](https://github.com/dan-petty/devops-cli/commit/3113ecfce631ec27d7c88f3abd76ed4388ec9f3f)), closes [#2252](https://github.com/dan-petty/devops-cli/issues/2252)
* **roadmap:** the Service sets the status label and adds Planned ([#2931](https://github.com/dan-petty/devops-cli/issues/2931)) ([8605473](https://github.com/dan-petty/devops-cli/commit/8605473af217cf73007b2a8d514d6eb855025059)), closes [#2920](https://github.com/dan-petty/devops-cli/issues/2920)

## [0.33.1](https://github.com/dan-petty/devops-cli/compare/v0.33.0...v0.33.1) (2026-10-31)


### Bug Fixes

* **k8s:** permit mattermost-operator and cnpg in homelab destinations ([#2927](https://github.com/dan-petty/devops-cli/issues/2927)) ([3c9102b](https://github.com/dan-petty/devops-cli/commit/3c9102ba1c1159507ced9c6a2e7cf7ab45b433cb))

## [0.33.0](https://github.com/dan-petty/devops-cli/compare/v0.32.0...v0.33.0) (2026-10-31)


### Features

* **docker:** preview requests in dry run for docker and sandbox commands ([#2923](https://github.com/dan-petty/devops-cli/issues/2923)) ([b35ac53](https://github.com/dan-petty/devops-cli/commit/b35ac532685cd304683446e38047da6a188bcbcf)), closes [#2251](https://github.com/dan-petty/devops-cli/issues/2251)
* **roadmap:** add mattermost /roadmap slash command ([#2914](https://github.com/dan-petty/devops-cli/issues/2914)) ([d669c15](https://github.com/dan-petty/devops-cli/commit/d669c151d9c8194bd62a0df742188dd3f845b6c6)), closes [#1395](https://github.com/dan-petty/devops-cli/issues/1395)
* **roadmap:** stage every Ready item, implement low effort ([#2924](https://github.com/dan-petty/devops-cli/issues/2924)) ([7950748](https://github.com/dan-petty/devops-cli/commit/7950748fc73d84902f91b3918c0ee782f988904a)), closes [#2906](https://github.com/dan-petty/devops-cli/issues/2906)
* **scan:** preview requests in dry run for scan commands ([#2903](https://github.com/dan-petty/devops-cli/issues/2903)) ([310322c](https://github.com/dan-petty/devops-cli/commit/310322c3f47364583e237bb97f159bca140e1fc8)), closes [#2250](https://github.com/dan-petty/devops-cli/issues/2250)

## [0.32.0](https://github.com/dan-petty/devops-cli/compare/v0.31.0...v0.32.0) (2026-10-31)


### Features

* **k8s:** argo cd posts deploy notifications to mattermost ([#2904](https://github.com/dan-petty/devops-cli/issues/2904)) ([6d9eff7](https://github.com/dan-petty/devops-cli/commit/6d9eff76da349e548cb93be1383c2962e5abffa6))
* **k8s:** post alertmanager alerts to mattermost ([#2897](https://github.com/dan-petty/devops-cli/issues/2897)) ([17c5295](https://github.com/dan-petty/devops-cli/commit/17c52957f30e13480024254953082204b1fe5a6f)), closes [#1392](https://github.com/dan-petty/devops-cli/issues/1392)


### Bug Fixes

* **security:** the subprocess environment guard accepts... ([#2901](https://github.com/dan-petty/devops-cli/issues/2901)) ([a508203](https://github.com/dan-petty/devops-cli/commit/a5082031c9f806f32e2e0f98684745286d5433b5))

## [0.31.0](https://github.com/dan-petty/devops-cli/compare/v0.30.0...v0.31.0) (2026-10-31)


### Features

* **terraform:** preview requests in dry run for tf commands ([#2895](https://github.com/dan-petty/devops-cli/issues/2895)) ([980a9be](https://github.com/dan-petty/devops-cli/commit/980a9be379b44fc27fdf9768238050b3769b3e71)), closes [#2249](https://github.com/dan-petty/devops-cli/issues/2249)


### Bug Fixes

* **security:** the subprocess environment guard accepts LESS, which... ([#2896](https://github.com/dan-petty/devops-cli/issues/2896)) ([1545b85](https://github.com/dan-petty/devops-cli/commit/1545b85ae7631a2238ad90991fc0927d21a67a02))

## [0.30.0](https://github.com/dan-petty/devops-cli/compare/v0.29.0...v0.30.0) (2026-10-31)


### Features

* **k8s:** mattermost team edition on cloudnativepg ([#2891](https://github.com/dan-petty/devops-cli/issues/2891)) ([c8e0948](https://github.com/dan-petty/devops-cli/commit/c8e0948e1c5d69b09287b842ce7ebc9c7d25dbc3))
* **review:** preview requests in dry run for review commands ([#2892](https://github.com/dan-petty/devops-cli/issues/2892)) ([69c1f26](https://github.com/dan-petty/devops-cli/commit/69c1f262fc6a93425b9e8281db18ffa75837b7c1)), closes [#2248](https://github.com/dan-petty/devops-cli/issues/2248)

## [0.29.0](https://github.com/dan-petty/devops-cli/compare/v0.28.0...v0.29.0) (2026-10-31)


### Features

* **ai:** declare local ai commands make no external request ([#2888](https://github.com/dan-petty/devops-cli/issues/2888)) ([306f016](https://github.com/dan-petty/devops-cli/commit/306f016b37aa44c1afa230063d16096759c7a00c)), closes [#2247](https://github.com/dan-petty/devops-cli/issues/2247)

## [0.28.0](https://github.com/dan-petty/devops-cli/compare/v0.27.0...v0.28.0) (2026-10-31)


### Features

* **ai:** preview requests in dry run for rag ingest analyze ([#2873](https://github.com/dan-petty/devops-cli/issues/2873)) ([c53bcec](https://github.com/dan-petty/devops-cli/commit/c53bcec9838d42c07ca4fe5902d2c37e2af2575f)), closes [#2244](https://github.com/dan-petty/devops-cli/issues/2244)
* **ai:** preview requests in dry run for runs cost cache ([#2884](https://github.com/dan-petty/devops-cli/issues/2884)) ([0df9777](https://github.com/dan-petty/devops-cli/commit/0df9777dbb66bd159f5443f6f4494e9b31def730))
* **roadmap:** the Service marks green stage drafts ready ([#2882](https://github.com/dan-petty/devops-cli/issues/2882)) ([63fae06](https://github.com/dan-petty/devops-cli/commit/63fae06b5e4f07630b4519fdde0be9d28944a5cc)), closes [#2865](https://github.com/dan-petty/devops-cli/issues/2865)
* **roadmap:** tool log names the reason of a retried call ([#2875](https://github.com/dan-petty/devops-cli/issues/2875)) ([03d3dc5](https://github.com/dan-petty/devops-cli/commit/03d3dc550e00374518f683c7275dedc091681c3d)), closes [#2866](https://github.com/dan-petty/devops-cli/issues/2866)


### Bug Fixes

* **ci:** devops ci test expands or refuses a path argument ([#2879](https://github.com/dan-petty/devops-cli/issues/2879)) ([884a80b](https://github.com/dan-petty/devops-cli/commit/884a80b5066672cfd87f55eb2cf8410dff298d27)), closes [#2868](https://github.com/dan-petty/devops-cli/issues/2868)
* **roadmap:** cap output and deadline of a step model call ([#2881](https://github.com/dan-petty/devops-cli/issues/2881)) ([0c4bd3a](https://github.com/dan-petty/devops-cli/commit/0c4bd3ae8a1314a3e356e32d2e73c8fdf79bbb85)), closes [#2869](https://github.com/dan-petty/devops-cli/issues/2869)

## [0.27.0](https://github.com/dan-petty/devops-cli/compare/v0.26.1...v0.27.0) (2026-10-31)


### Features

* **ai:** preview requests in dry run for model and gateway ([#2862](https://github.com/dan-petty/devops-cli/issues/2862)) ([efd6159](https://github.com/dan-petty/devops-cli/commit/efd615964d281fabb8b9035181aa2bd78218d1df)), closes [#2241](https://github.com/dan-petty/devops-cli/issues/2241)
* **argo:** preview requests in dry run for argo commands ([#2855](https://github.com/dan-petty/devops-cli/issues/2855)) ([9b18d68](https://github.com/dan-petty/devops-cli/commit/9b18d683445ef2e210a443d28a5506b56a29639a)), closes [#2240](https://github.com/dan-petty/devops-cli/issues/2240)
* **k8s:** preview requests in dry run for manifest commands ([#2851](https://github.com/dan-petty/devops-cli/issues/2851)) ([92be95c](https://github.com/dan-petty/devops-cli/commit/92be95c7e8c0ec940e8bba0ee43a72bbe4df05ab)), closes [#2239](https://github.com/dan-petty/devops-cli/issues/2239)

## [0.26.1](https://github.com/dan-petty/devops-cli/compare/v0.26.0...v0.26.1) (2026-10-31)


### Bug Fixes

* **ci:** allow only declared scopes in pull request titles ([#2846](https://github.com/dan-petty/devops-cli/issues/2846)) ([f6aea38](https://github.com/dan-petty/devops-cli/commit/f6aea380ceacd5bf9bde13d6ea0e49bff082f093)), closes [#2800](https://github.com/dan-petty/devops-cli/issues/2800)
* **security:** remove pre-flight resolve paths for egress ([#2845](https://github.com/dan-petty/devops-cli/issues/2845)) ([6ebc968](https://github.com/dan-petty/devops-cli/commit/6ebc9683abcc8501aa9e1c39c19cd3c3128d9d46)), closes [#2437](https://github.com/dan-petty/devops-cli/issues/2437)

## [0.26.0](https://github.com/dan-petty/devops-cli/compare/v0.25.0...v0.26.0) (2026-10-31)


### Features

* **k8s:** preview requests in dry run for cluster commands ([#2839](https://github.com/dan-petty/devops-cli/issues/2839)) ([b6de1a4](https://github.com/dan-petty/devops-cli/commit/b6de1a46a3162d9dfd5255c4f74e9068f1343966)), closes [#2238](https://github.com/dan-petty/devops-cli/issues/2238)
* **pr:** preview requests in dry run for pr commands ([#2835](https://github.com/dan-petty/devops-cli/issues/2835)) ([2a9b746](https://github.com/dan-petty/devops-cli/commit/2a9b746b86a45307d98bd9309944ec1a1b49e456)), closes [#2234](https://github.com/dan-petty/devops-cli/issues/2234)


### Bug Fixes

* **k8s:** enforce the window of each gateway deployment ([#2843](https://github.com/dan-petty/devops-cli/issues/2843)) ([2ff7d9f](https://github.com/dan-petty/devops-cli/commit/2ff7d9fd2026342f9d358b87bc2ac8ec9073b44d)), closes [#2825](https://github.com/dan-petty/devops-cli/issues/2825)
* **roadmap:** measure a task group by the files its step reads ([#2847](https://github.com/dan-petty/devops-cli/issues/2847)) ([2f3986a](https://github.com/dan-petty/devops-cli/commit/2f3986a71bbba9f9d6e919f31feb4380d849ca16)), closes [#2838](https://github.com/dan-petty/devops-cli/issues/2838)
* **tests:** replace real test sleeps with clock ([#2169](https://github.com/dan-petty/devops-cli/issues/2169)) ([#2833](https://github.com/dan-petty/devops-cli/issues/2833)) ([506f769](https://github.com/dan-petty/devops-cli/commit/506f7692457075f31a1e399d9a59c8ee309f5ced))

## [0.25.0](https://github.com/dan-petty/devops-cli/compare/v0.24.0...v0.25.0) (2026-10-31)


### Features

* **gh:** preview requests in dry run for api, status, secrets ([#2832](https://github.com/dan-petty/devops-cli/issues/2832)) ([9baf3dd](https://github.com/dan-petty/devops-cli/commit/9baf3ddf6b0c3b768d1e5832ff420796601dd0d9)), closes [#2237](https://github.com/dan-petty/devops-cli/issues/2237)
* **gh:** preview requests in dry run for issues, labels, runs ([#2826](https://github.com/dan-petty/devops-cli/issues/2826)) ([c58a50d](https://github.com/dan-petty/devops-cli/commit/c58a50d6a318f7c6f82e466f95635fdc54517bb1)), closes [#2235](https://github.com/dan-petty/devops-cli/issues/2235)


### Bug Fixes

* **config:** preserve file mode on write and copy ([#2831](https://github.com/dan-petty/devops-cli/issues/2831)) ([8028319](https://github.com/dan-petty/devops-cli/commit/8028319e1e48830fd78cb98967003ba90cb6ddee)), closes [#2745](https://github.com/dan-petty/devops-cli/issues/2745)
* **config:** report a clear error for merge-key unset ([#2828](https://github.com/dan-petty/devops-cli/issues/2828)) ([7514766](https://github.com/dan-petty/devops-cli/commit/75147663b634ec89fbf0808786be33702c2a28ab)), closes [#2656](https://github.com/dan-petty/devops-cli/issues/2656)

## [0.24.0](https://github.com/dan-petty/devops-cli/compare/v0.23.0...v0.24.0) (2026-10-31)


### Features

* **cli:** declare dry-run class and enforce with ratchet test ([#2817](https://github.com/dan-petty/devops-cli/issues/2817)) ([840d3eb](https://github.com/dan-petty/devops-cli/commit/840d3eb29bd7622286b0c6c3fb002229f3232f7c)), closes [#2230](https://github.com/dan-petty/devops-cli/issues/2230)
* **gh:** list dry-run requests in project, views and pages ([#2820](https://github.com/dan-petty/devops-cli/issues/2820)) ([6a9a24e](https://github.com/dan-petty/devops-cli/commit/6a9a24e1dd39a56f6f60a531d1fa485680967bf9)), closes [#2236](https://github.com/dan-petty/devops-cli/issues/2236)
* **k8s:** raise the context of the condor and hawk Ollama tiers ([#2824](https://github.com/dan-petty/devops-cli/issues/2824)) ([325fbdb](https://github.com/dan-petty/devops-cli/commit/325fbdbd2539c8403eed09a3b76c4ba338a83a56)), closes [#2822](https://github.com/dan-petty/devops-cli/issues/2822)


### Bug Fixes

* **ci:** the scope git of a pull request title has no label ([#2821](https://github.com/dan-petty/devops-cli/issues/2821)) ([2c5ae30](https://github.com/dan-petty/devops-cli/commit/2c5ae3099df3463e3bfe0f1ccb811d1f7a8e1708)), closes [#2800](https://github.com/dan-petty/devops-cli/issues/2800)
* **github:** treat the traffic API 403 as expected ([#2823](https://github.com/dan-petty/devops-cli/issues/2823)) ([e66a124](https://github.com/dan-petty/devops-cli/commit/e66a1247c1948d87033f0686ed735b58bb62cc41)), closes [#2626](https://github.com/dan-petty/devops-cli/issues/2626)

## [0.23.0](https://github.com/dan-petty/devops-cli/compare/v0.22.7...v0.23.0) (2026-10-31)


### Features

* **review:** confirm finding on human VERIFIED verdict ([#2813](https://github.com/dan-petty/devops-cli/issues/2813)) ([26203af](https://github.com/dan-petty/devops-cli/commit/26203af4a8bf65d00c736e08e98b20f94445034a)), closes [#2414](https://github.com/dan-petty/devops-cli/issues/2414)
* **roadmap:** intake runs in triage lane on devops-triage model ([#2816](https://github.com/dan-petty/devops-cli/issues/2816)) ([35e6172](https://github.com/dan-petty/devops-cli/commit/35e61725ecc33d965cbdb8fe6351741e7688d131)), closes [#1534](https://github.com/dan-petty/devops-cli/issues/1534)
* **roadmap:** link candidate from source as a sub-issue ([#2812](https://github.com/dan-petty/devops-cli/issues/2812)) ([aee2c85](https://github.com/dan-petty/devops-cli/commit/aee2c8573141c0348a60f59809dc57ef008aa8bc)), closes [#2035](https://github.com/dan-petty/devops-cli/issues/2035)
* **service:** each subscribed webhook event runs its scoped update ([#2811](https://github.com/dan-petty/devops-cli/issues/2811)) ([0564c08](https://github.com/dan-petty/devops-cli/commit/0564c088701af87e64d07a09ba3a07050d9bff63)), closes [#1533](https://github.com/dan-petty/devops-cli/issues/1533)


### Bug Fixes

* **config:** config files and their copies keep the mode of the file,... ([#2801](https://github.com/dan-petty/devops-cli/issues/2801)) ([72b82e3](https://github.com/dan-petty/devops-cli/commit/72b82e38795ed162276e274d9da48cd2acbd86a2))
* **k8s:** bound the test workers and log the command of a step ([#2809](https://github.com/dan-petty/devops-cli/issues/2809)) ([2314ef9](https://github.com/dan-petty/devops-cli/commit/2314ef987f367f7428be8899e1504189888919ff)), closes [#2806](https://github.com/dan-petty/devops-cli/issues/2806)
* **roadmap:** a step may not lose a test that existed ([#2807](https://github.com/dan-petty/devops-cli/issues/2807)) ([7d104a5](https://github.com/dan-petty/devops-cli/commit/7d104a5483a3acf335c1032c301ad238593a7a2e)), closes [#2804](https://github.com/dan-petty/devops-cli/issues/2804)
* **security:** lock graphql-core at 3.3.1 and pyasn1 at 0.6.5 ([#2814](https://github.com/dan-petty/devops-cli/issues/2814)) ([8234a83](https://github.com/dan-petty/devops-cli/commit/8234a837f74d2fc0dcfc61e260c3da78bbf07bc8)), closes [#2808](https://github.com/dan-petty/devops-cli/issues/2808)


### Code Refactoring

* **ai:** seams and fakes for Valkey, Qdrant and embedder ([#2815](https://github.com/dan-petty/devops-cli/issues/2815)) ([1e03417](https://github.com/dan-petty/devops-cli/commit/1e03417f42947617062329cef26e32431320f3d6)), closes [#1317](https://github.com/dan-petty/devops-cli/issues/1317)


### Reverts

* fix(config): config files and their copies keep the mode... ([#2805](https://github.com/dan-petty/devops-cli/issues/2805)) ([6c50285](https://github.com/dan-petty/devops-cli/commit/6c502854d76ec26fd52177e0c4266abdbffdda90))

## [0.22.7](https://github.com/dan-petty/devops-cli/compare/v0.22.6...v0.22.7) (2026-10-30)


### Bug Fixes

* **roadmap:** a failed ruff or mypy check gets one repair turn ([#2796](https://github.com/dan-petty/devops-cli/issues/2796)) ([77e7f7c](https://github.com/dan-petty/devops-cli/commit/77e7f7c4f51f2730697f91886ab59cfdff51a414)), closes [#2795](https://github.com/dan-petty/devops-cli/issues/2795)
* **roadmap:** show the 400 body and resend a failed stream once ([#2797](https://github.com/dan-petty/devops-cli/issues/2797)) ([034aa0e](https://github.com/dan-petty/devops-cli/commit/034aa0e672998c70239f3c871f5884c743dc3277)), closes [#2794](https://github.com/dan-petty/devops-cli/issues/2794)

## [0.22.6](https://github.com/dan-petty/devops-cli/compare/v0.22.5...v0.22.6) (2026-10-30)


### Bug Fixes

* **roadmap:** format changed Python files in the job ([#2791](https://github.com/dan-petty/devops-cli/issues/2791)) ([18a6e2b](https://github.com/dan-petty/devops-cli/commit/18a6e2bfa2b8ec8136ee699814d0fa5b3aa1f588)), closes [#2789](https://github.com/dan-petty/devops-cli/issues/2789)
* **roadmap:** the job owns tasks.md in an implement step ([#2792](https://github.com/dan-petty/devops-cli/issues/2792)) ([2e9552f](https://github.com/dan-petty/devops-cli/commit/2e9552f433e85a0dffc7a2d2f3502dfa42f410a4)), closes [#2790](https://github.com/dan-petty/devops-cli/issues/2790)

## [0.22.5](https://github.com/dan-petty/devops-cli/compare/v0.22.4...v0.22.5) (2026-10-30)


### Bug Fixes

* **roadmap:** keep the diff of a step when a model call fails ([#2781](https://github.com/dan-petty/devops-cli/issues/2781)) ([c6a837d](https://github.com/dan-petty/devops-cli/commit/c6a837d3afd274c647de87f3c093dacd2125c50f)), closes [#2731](https://github.com/dan-petty/devops-cli/issues/2731)
* **roadmap:** name the repo and cause in refine warnings ([#2784](https://github.com/dan-petty/devops-cli/issues/2784)) ([85b3a67](https://github.com/dan-petty/devops-cli/commit/85b3a67bb98d732704c689bf6346ecb1aa7168e5)), closes [#2562](https://github.com/dan-petty/devops-cli/issues/2562)

## [0.22.4](https://github.com/dan-petty/devops-cli/compare/v0.22.3...v0.22.4) (2026-10-30)


### Bug Fixes

* **pr:** pr create adds the labels of the title ([#2782](https://github.com/dan-petty/devops-cli/issues/2782)) ([7183af3](https://github.com/dan-petty/devops-cli/commit/7183af3911b832a671a97fd3b50482b45a808d54)), closes [#2748](https://github.com/dan-petty/devops-cli/issues/2748)
* **roadmap:** refused shell programs name their replacement ([#2783](https://github.com/dan-petty/devops-cli/issues/2783)) ([0458f8f](https://github.com/dan-petty/devops-cli/commit/0458f8f525798feef3305bfc12eb3645a766363c)), closes [#2773](https://github.com/dan-petty/devops-cli/issues/2773)
* **roadmap:** restore the own group text in an implement step ([#2780](https://github.com/dan-petty/devops-cli/issues/2780)) ([163a840](https://github.com/dan-petty/devops-cli/commit/163a8409032c48581d6169f6a6028207d218ccdf)), closes [#2774](https://github.com/dan-petty/devops-cli/issues/2774)
* **security:** lock joserfc at 1.7.7 ([#2787](https://github.com/dan-petty/devops-cli/issues/2787)) ([0b9f9e5](https://github.com/dan-petty/devops-cli/commit/0b9f9e5add219a8a97e0cbf63f645baaa5ce37dc)), closes [#2786](https://github.com/dan-petty/devops-cli/issues/2786)

## [0.22.3](https://github.com/dan-petty/devops-cli/compare/v0.22.2...v0.22.3) (2026-10-30)


### Bug Fixes

* **roadmap:** a stage group names its files and its tasks ([#2775](https://github.com/dan-petty/devops-cli/issues/2775)) ([15ca3a3](https://github.com/dan-petty/devops-cli/commit/15ca3a37b1478b908210c927a6758d4e091f13d8)), closes [#2772](https://github.com/dan-petty/devops-cli/issues/2772)

## [0.22.2](https://github.com/dan-petty/devops-cli/compare/v0.22.1...v0.22.2) (2026-10-30)


### Bug Fixes

* **release:** the urgent-fix rule reads scope/security, not type/security ([#2769](https://github.com/dan-petty/devops-cli/issues/2769)) ([05be980](https://github.com/dan-petty/devops-cli/commit/05be980e558fca3209cacdb7d4111831be0e7e5c))
* **roadmap:** restore ticks of other groups in an implement step ([#2770](https://github.com/dan-petty/devops-cli/issues/2770)) ([c266ce2](https://github.com/dan-petty/devops-cli/commit/c266ce2ca5b5ee951daf131f56547c5bb0c149e0)), closes [#2767](https://github.com/dan-petty/devops-cli/issues/2767)

## [0.22.1](https://github.com/dan-petty/devops-cli/compare/v0.22.0...v0.22.1) (2026-10-30)


### Bug Fixes

* **github:** ask no traffic endpoint as the App ([#2759](https://github.com/dan-petty/devops-cli/issues/2759)) ([692c15f](https://github.com/dan-petty/devops-cli/commit/692c15fad0c945598230c6ac57017ddb3e8a54e7)), closes [#2752](https://github.com/dan-petty/devops-cli/issues/2752)
* **roadmap:** a stop of the Service is not a failed round ([#2756](https://github.com/dan-petty/devops-cli/issues/2756)) ([0b7e190](https://github.com/dan-petty/devops-cli/commit/0b7e190e9c655150caea12fbdfaa716950032f15)), closes [#2753](https://github.com/dan-petty/devops-cli/issues/2753)
* **roadmap:** say why an implement step stopped ([#2762](https://github.com/dan-petty/devops-cli/issues/2762)) ([cd56ce4](https://github.com/dan-petty/devops-cli/commit/cd56ce4358b86c814e6ad3e36153da2f4246e321)), closes [#2758](https://github.com/dan-petty/devops-cli/issues/2758)
* **service:** render and alert on the hourly request budget ([#2760](https://github.com/dan-petty/devops-cli/issues/2760)) ([809d85b](https://github.com/dan-petty/devops-cli/commit/809d85b7f0f471f053c953ce39a65e8800ed8d0b)), closes [#2755](https://github.com/dan-petty/devops-cli/issues/2755)
* **service:** run the implement row on the status lane ([#2763](https://github.com/dan-petty/devops-cli/issues/2763)) ([cd94f2c](https://github.com/dan-petty/devops-cli/commit/cd94f2cea3cffc7e26d19feb4462d70531758129)), closes [#2757](https://github.com/dan-petty/devops-cli/issues/2757)


### Performance Improvements

* **ci:** cut test job time and guard its mean ([#2764](https://github.com/dan-petty/devops-cli/issues/2764)) ([e76f656](https://github.com/dan-petty/devops-cli/commit/e76f656cbc580542ce8b548142aaac056ebabcac)), closes [#2699](https://github.com/dan-petty/devops-cli/issues/2699)

## [0.22.0](https://github.com/dan-petty/devops-cli/compare/v0.21.4...v0.22.0) (2026-10-30)


### Features

* **k8s:** admission policy for the Service Jobs ([#2730](https://github.com/dan-petty/devops-cli/issues/2730)) ([4be83c2](https://github.com/dan-petty/devops-cli/commit/4be83c28b69b6b0011dd743c242ea2897da618a6)), closes [#2696](https://github.com/dan-petty/devops-cli/issues/2696)


### Bug Fixes

* **security:** refuse the uv and npm keys that run a program ([#2749](https://github.com/dan-petty/devops-cli/issues/2749)) ([c5a4596](https://github.com/dan-petty/devops-cli/commit/c5a45965d4514b690da2c961b98204a401bcb67d)), closes [#2673](https://github.com/dan-petty/devops-cli/issues/2673)

## [0.21.4](https://github.com/dan-petty/devops-cli/compare/v0.21.3...v0.21.4) (2026-10-30)


### Bug Fixes

* **ai:** name each prewarm server by host and port ([#2737](https://github.com/dan-petty/devops-cli/issues/2737)) ([2e2e4fa](https://github.com/dan-petty/devops-cli/commit/2e2e4fac35935dcfadecb0f61001149a70e16fa8)), closes [#2676](https://github.com/dan-petty/devops-cli/issues/2676)
* **ai:** the mcp benchmark tool takes no file path ([#2738](https://github.com/dan-petty/devops-cli/issues/2738)) ([5d5da15](https://github.com/dan-petty/devops-cli/commit/5d5da15ad20137be749557546227c30b952f59fc)), closes [#2704](https://github.com/dan-petty/devops-cli/issues/2704)
* **config:** redact a removed credential in the config copies ([#2734](https://github.com/dan-petty/devops-cli/issues/2734)) ([f663344](https://github.com/dan-petty/devops-cli/commit/f663344b5b934c6bd64e436036e204c1641907c7)), closes [#2645](https://github.com/dan-petty/devops-cli/issues/2645)
* **rag:** name the Qdrant server by host and port ([#2733](https://github.com/dan-petty/devops-cli/issues/2733)) ([39aca9d](https://github.com/dan-petty/devops-cli/commit/39aca9d7dffa8ebb3cb24553ab39ac8297c212ea)), closes [#2709](https://github.com/dan-petty/devops-cli/issues/2709)
* **roadmap:** tick turn and kept diff for implement steps ([#2744](https://github.com/dan-petty/devops-cli/issues/2744)) ([890d2a6](https://github.com/dan-petty/devops-cli/commit/890d2a62e4e3b33a99bb88b9df6c3a67f89a24a5)), closes [#2721](https://github.com/dan-petty/devops-cli/issues/2721)
* **security:** refuse the gh and kubectl keys that run a program ([#2732](https://github.com/dan-petty/devops-cli/issues/2732)) ([ad0bdf1](https://github.com/dan-petty/devops-cli/commit/ad0bdf1fc2db9acc02b4d432250954902b46a2d5)), closes [#2672](https://github.com/dan-petty/devops-cli/issues/2672)
* **security:** refuse the keys that make a child write a file ([#2746](https://github.com/dan-petty/devops-cli/issues/2746)) ([1cd187e](https://github.com/dan-petty/devops-cli/commit/1cd187e9e4c999cf02ef5541343044196d6608b2)), closes [#2674](https://github.com/dan-petty/devops-cli/issues/2674)

## [0.21.3](https://github.com/dan-petty/devops-cli/compare/v0.21.2...v0.21.3) (2026-10-30)


### Bug Fixes

* **repos:** clear a stray local branch before worktree add ([#2727](https://github.com/dan-petty/devops-cli/issues/2727)) ([34136cb](https://github.com/dan-petty/devops-cli/commit/34136cbc978a7af4b273aaf8ae27801c0311bb9a)), closes [#2724](https://github.com/dan-petty/devops-cli/issues/2724)

## [0.21.2](https://github.com/dan-petty/devops-cli/compare/v0.21.1...v0.21.2) (2026-10-30)


### Bug Fixes

* **roadmap:** the status label follows the pull request ([#2723](https://github.com/dan-petty/devops-cli/issues/2723)) ([4435a21](https://github.com/dan-petty/devops-cli/commit/4435a21916cec508c1072fcc5caa6d52bd0c1de0)), closes [#2717](https://github.com/dan-petty/devops-cli/issues/2717)

## [0.21.1](https://github.com/dan-petty/devops-cli/compare/v0.21.0...v0.21.1) (2026-10-30)


### Bug Fixes

* **roadmap:** intake derives type and scope labels from the title ([#2720](https://github.com/dan-petty/devops-cli/issues/2720)) ([5278c53](https://github.com/dan-petty/devops-cli/commit/5278c53e9d88ce95f6ff6e395151720a868ef768)), closes [#2715](https://github.com/dan-petty/devops-cli/issues/2715)

## [0.21.0](https://github.com/dan-petty/devops-cli/compare/v0.20.0...v0.21.0) (2026-10-29)


### Features

* **telemetry:** count the project items by release tag, not by milestone ([#2710](https://github.com/dan-petty/devops-cli/issues/2710)) ([253a97d](https://github.com/dan-petty/devops-cli/commit/253a97d48b306a95c1a73285fe593818a1d1b983))


### Bug Fixes

* **ai:** the MCP benchmark tool takes no server URL ([#2707](https://github.com/dan-petty/devops-cli/issues/2707)) ([7f7f84b](https://github.com/dan-petty/devops-cli/commit/7f7f84b9dc1b439f94e675cd687912f033330aba)), closes [#2638](https://github.com/dan-petty/devops-cli/issues/2638)
* **rag:** name the Qdrant span server by host and port ([#2705](https://github.com/dan-petty/devops-cli/issues/2705)) ([57725c3](https://github.com/dan-petty/devops-cli/commit/57725c3a98c923639adcaa53df47a57314512d6e)), closes [#2459](https://github.com/dan-petty/devops-cli/issues/2459)
* report a clear error for a merge-key unset ([#2697](https://github.com/dan-petty/devops-cli/issues/2697)) ([676d505](https://github.com/dan-petty/devops-cli/commit/676d505e30c206c48d585da4d56937a7bd51899f))
* **roadmap:** take a plan that a person merged as a Planned item ([#2718](https://github.com/dan-petty/devops-cli/issues/2718)) ([043463b](https://github.com/dan-petty/devops-cli/commit/043463b6e8667b18303d9ec252ee0763c9240079)), closes [#2714](https://github.com/dan-petty/devops-cli/issues/2714)
* **security:** pin tflint; remove dive and devops docker analyze-layers ([#2712](https://github.com/dan-petty/devops-cli/issues/2712)) ([244bafb](https://github.com/dan-petty/devops-cli/commit/244bafbf964bdb1f60a02abce1f39690e1c42937))
* **vault:** the MCP tool vault_status takes no address ([#2706](https://github.com/dan-petty/devops-cli/issues/2706)) ([68c226c](https://github.com/dan-petty/devops-cli/commit/68c226c03aa75c02deb8516efdcbe5c03bd87e35)), closes [#2639](https://github.com/dan-petty/devops-cli/issues/2639)


### Reverts

* "fix: report a clear error for a merge-key unset" ([#2716](https://github.com/dan-petty/devops-cli/issues/2716)) ([bf5cf0e](https://github.com/dan-petty/devops-cli/commit/bf5cf0e8a0963bb04e316e4928f4b14d1c377d19))

## [0.20.0](https://github.com/dan-petty/devops-cli/compare/v0.19.0...v0.20.0) (2026-10-29)


### Features

* **roadmap:** run the implement job as a cluster Job ([#2698](https://github.com/dan-petty/devops-cli/issues/2698)) ([b4669f6](https://github.com/dan-petty/devops-cli/commit/b4669f653ad74d16f66621783eb94277636286b0)), closes [#2667](https://github.com/dan-petty/devops-cli/issues/2667)

## [0.19.0](https://github.com/dan-petty/devops-cli/compare/v0.18.0...v0.19.0) (2026-10-29)


### Features

* **roadmap:** add the implement job to roadmap implement ([#2692](https://github.com/dan-petty/devops-cli/issues/2692)) ([9c7a5f5](https://github.com/dan-petty/devops-cli/commit/9c7a5f50048558d8ecb7e8e12b945c05a4eeeae0)), closes [#2665](https://github.com/dan-petty/devops-cli/issues/2665)
* **roadmap:** run the alternatives check as a Service row ([#2688](https://github.com/dan-petty/devops-cli/issues/2688)) ([c462318](https://github.com/dan-petty/devops-cli/commit/c462318850a391bd9e42c2defebf3bb9f914979d)), closes [#2652](https://github.com/dan-petty/devops-cli/issues/2652)
* **roadmap:** run the stage job as a Service row ([#2691](https://github.com/dan-petty/devops-cli/issues/2691)) ([a8d5f0e](https://github.com/dan-petty/devops-cli/commit/a8d5f0ec1b4bcd09901b13b59104104bc2ca2af1)), closes [#2659](https://github.com/dan-petty/devops-cli/issues/2659)


### Bug Fixes

* **ci:** re-pin every CI runner to ubuntu-26.04 ([#2693](https://github.com/dan-petty/devops-cli/issues/2693)) ([31fe55c](https://github.com/dan-petty/devops-cli/commit/31fe55cb4aeb3478e4131d4137a708d5fae71bf6)), closes [#1501](https://github.com/dan-petty/devops-cli/issues/1501)

## [0.18.0](https://github.com/dan-petty/devops-cli/compare/v0.17.0...v0.18.0) (2026-10-29)


### Features

* **roadmap:** add devops roadmap stage for Ready items ([#2686](https://github.com/dan-petty/devops-cli/issues/2686)) ([abd016d](https://github.com/dan-petty/devops-cli/commit/abd016db346186326e9af30ff0d603406f9192e2)), closes [#2654](https://github.com/dan-petty/devops-cli/issues/2654)
* **roadmap:** add the devops roadmap implement command ([#2684](https://github.com/dan-petty/devops-cli/issues/2684)) ([11b7cb5](https://github.com/dan-petty/devops-cli/commit/11b7cb538cb3d38c95a48273649e6866af77be52)), closes [#2664](https://github.com/dan-petty/devops-cli/issues/2664)

## [0.17.0](https://github.com/dan-petty/devops-cli/compare/v0.16.7...v0.17.0) (2026-10-29)


### Features

* **repos:** worktrees add takes over a staged branch ([#2675](https://github.com/dan-petty/devops-cli/issues/2675)) ([03eadec](https://github.com/dan-petty/devops-cli/commit/03eadecf24a85d28ebcc6d88a1b80b511ea73fb2)), closes [#2657](https://github.com/dan-petty/devops-cli/issues/2657)
* **roadmap:** check open items for open alternative tools ([#2681](https://github.com/dan-petty/devops-cli/issues/2681)) ([4f993dc](https://github.com/dan-petty/devops-cli/commit/4f993dce369bc587b174d5fa3e6fa6fcb898f39c)), closes [#2650](https://github.com/dan-petty/devops-cli/issues/2650)


### Bug Fixes

* **security:** refuse the library keys that load a module ([#2682](https://github.com/dan-petty/devops-cli/issues/2682)) ([e681884](https://github.com/dan-petty/devops-cli/commit/e6818847e96b9c111068d93ed31f3715ee8a334a)), closes [#2503](https://github.com/dan-petty/devops-cli/issues/2503)

## [0.16.7](https://github.com/dan-petty/devops-cli/compare/v0.16.6...v0.16.7) (2026-10-29)


### Bug Fixes

* **security:** the guard refuses the ssh keys and SHELL ([#2678](https://github.com/dan-petty/devops-cli/issues/2678)) ([7f85930](https://github.com/dan-petty/devops-cli/commit/7f85930f29cc7a44fe74a3bf04a825939bd1a123)), closes [#2633](https://github.com/dan-petty/devops-cli/issues/2633)

## [0.16.6](https://github.com/dan-petty/devops-cli/compare/v0.16.5...v0.16.6) (2026-10-29)


### Bug Fixes

* **ai:** the MCP prewarm tool takes no URL from the model ([#2677](https://github.com/dan-petty/devops-cli/issues/2677)) ([edf5325](https://github.com/dan-petty/devops-cli/commit/edf5325751d383b83e8b25673b7130670407118e)), closes [#2637](https://github.com/dan-petty/devops-cli/issues/2637)

## [0.16.5](https://github.com/dan-petty/devops-cli/compare/v0.16.4...v0.16.5) (2026-10-29)


### Bug Fixes

* **ai:** name benchmark servers and models by host and port ([#2666](https://github.com/dan-petty/devops-cli/issues/2666)) ([8a08031](https://github.com/dan-petty/devops-cli/commit/8a0803135112ab9163ffa2a9fdfaf75d2ceae801)), closes [#2481](https://github.com/dan-petty/devops-cli/issues/2481)
* **config:** the audit-keys alert names the removal commands ([#2663](https://github.com/dan-petty/devops-cli/issues/2663)) ([3eb138d](https://github.com/dan-petty/devops-cli/commit/3eb138d063faa65c9ab65b4d6161acb683cb0833)), closes [#2513](https://github.com/dan-petty/devops-cli/issues/2513)
* **k8s:** the MCP tool k8s_logs takes no Loki URL ([#2668](https://github.com/dan-petty/devops-cli/issues/2668)) ([39fae85](https://github.com/dan-petty/devops-cli/commit/39fae855b0efd5172702f81665bb0d7e3605fdac)), closes [#2635](https://github.com/dan-petty/devops-cli/issues/2635)

## [0.16.4](https://github.com/dan-petty/devops-cli/compare/v0.16.3...v0.16.4) (2026-10-29)


### Bug Fixes

* **valkey:** the MCP Valkey tools take no URL from the model ([#2655](https://github.com/dan-petty/devops-cli/issues/2655)) ([5bb1ed0](https://github.com/dan-petty/devops-cli/commit/5bb1ed0fe197f14b749aee13df33e0956b0e9c0c)), closes [#2634](https://github.com/dan-petty/devops-cli/issues/2634)

## [0.16.3](https://github.com/dan-petty/devops-cli/compare/v0.16.2...v0.16.3) (2026-10-29)


### Bug Fixes

* **security:** a failed shodan internetdb lookup is no ok record ([#2647](https://github.com/dan-petty/devops-cli/issues/2647)) ([ca9c1ad](https://github.com/dan-petty/devops-cli/commit/ca9c1ad7c59236b2d9894a07329010cdb163026d)), closes [#2504](https://github.com/dan-petty/devops-cli/issues/2504)

## [0.16.2](https://github.com/dan-petty/devops-cli/compare/v0.16.1...v0.16.2) (2026-10-29)


### Bug Fixes

* **security:** refuse the git keys that make git run a program ([#2641](https://github.com/dan-petty/devops-cli/issues/2641)) ([b4b1277](https://github.com/dan-petty/devops-cli/commit/b4b127710f3f99a551b47a7a315c24209b993a8b)), closes [#2483](https://github.com/dan-petty/devops-cli/issues/2483)

## [0.16.1](https://github.com/dan-petty/devops-cli/compare/v0.16.0...v0.16.1) (2026-10-29)


### Bug Fixes

* **ai:** the MCP gateway tools take no URL and guard the AI key ([#2640](https://github.com/dan-petty/devops-cli/issues/2640)) ([7dde54e](https://github.com/dan-petty/devops-cli/commit/7dde54e8a284ed29d4a4a1ba6fa28aa4e3f2643e)), closes [#2480](https://github.com/dan-petty/devops-cli/issues/2480)

## [0.16.0](https://github.com/dan-petty/devops-cli/compare/v0.15.1...v0.16.0) (2026-10-29)


### Features

* **service:** the Service keeps one model call in flight by default ([#2627](https://github.com/dan-petty/devops-cli/issues/2627)) ([3fdafbd](https://github.com/dan-petty/devops-cli/commit/3fdafbd70a17604a7788bb3a28095e8f9b32a4b9))


### Bug Fixes

* **config:** remove the dead cloudflare.access settings ([#2632](https://github.com/dan-petty/devops-cli/issues/2632)) ([dde2f55](https://github.com/dan-petty/devops-cli/commit/dde2f55b970a7bca5799fdbb0bb47ca9e0547d19))
* **roadmap:** read only the last comment as the job record ([#2630](https://github.com/dan-petty/devops-cli/issues/2630)) ([a3eb41f](https://github.com/dan-petty/devops-cli/commit/a3eb41f4ca6e58ceeed77b159eb910a3b3151b7a)), closes [#2538](https://github.com/dan-petty/devops-cli/issues/2538)
* **service:** check the GitHub budget for each request ([#2631](https://github.com/dan-petty/devops-cli/issues/2631)) ([99066e7](https://github.com/dan-petty/devops-cli/commit/99066e7a1de937c1c597d6f70e827af79bd8768e))
* **telemetry:** enable remote write 2.0 for created timestamps ([#2629](https://github.com/dan-petty/devops-cli/issues/2629)) ([e84a643](https://github.com/dan-petty/devops-cli/commit/e84a6430b9d82f6e91dd7177c839303de42b6324)), closes [#2506](https://github.com/dan-petty/devops-cli/issues/2506)

## [0.15.1](https://github.com/dan-petty/devops-cli/compare/v0.15.0...v0.15.1) (2026-10-29)


### Bug Fixes

* **k8s:** delete loki-ingress, blocked by the logging network policy ([#2624](https://github.com/dan-petty/devops-cli/issues/2624)) ([7c956e3](https://github.com/dan-petty/devops-cli/commit/7c956e300814bfe96f0919b462fb2fc3ef00666a)), closes [#2439](https://github.com/dan-petty/devops-cli/issues/2439)

## [0.15.0](https://github.com/dan-petty/devops-cli/compare/v0.14.0...v0.15.0) (2026-10-29)


### Features

* **k8s:** derived push entries, Secret types, one stack list ([#2618](https://github.com/dan-petty/devops-cli/issues/2618)) ([3634c6f](https://github.com/dan-petty/devops-cli/commit/3634c6f2d287b99e332ca47fe34c0a92a79f36a6)), closes [#2008](https://github.com/dan-petty/devops-cli/issues/2008)
* **k8s:** image-pins refuses an image on the latest tag ([#2617](https://github.com/dan-petty/devops-cli/issues/2617)) ([548b3ba](https://github.com/dan-petty/devops-cli/commit/548b3bae52956be619d3dd9e0dfe708edef10539)), closes [#2093](https://github.com/dan-petty/devops-cli/issues/2093)
* **monitoring:** alert when a noeviction Valkey nears its bound ([#2615](https://github.com/dan-petty/devops-cli/issues/2615)) ([f452644](https://github.com/dan-petty/devops-cli/commit/f4526446a370af2886b6719f915967e9cd1a645c)), closes [#2094](https://github.com/dan-petty/devops-cli/issues/2094)
* **review:** golangci-lint runs offline in the review sandbox ([#2622](https://github.com/dan-petty/devops-cli/issues/2622)) ([20915ce](https://github.com/dan-petty/devops-cli/commit/20915cee074f3c787ad1a86a9fc3046891241d5d)), closes [#2129](https://github.com/dan-petty/devops-cli/issues/2129)
* **review:** the SARIF export writes how each tool run ended ([#2620](https://github.com/dan-petty/devops-cli/issues/2620)) ([8f8ef44](https://github.com/dan-petty/devops-cli/commit/8f8ef449db711324bb597cb267ecbddd335f6e73)), closes [#2100](https://github.com/dan-petty/devops-cli/issues/2100)


### Bug Fixes

* **release:** parse release pull request number safely in urgent merge ([#2621](https://github.com/dan-petty/devops-cli/issues/2621)) ([262244d](https://github.com/dan-petty/devops-cli/commit/262244d91c9c414770dc0374a724691366c50daf))

## [0.14.0](https://github.com/dan-petty/devops-cli/compare/v0.13.2...v0.14.0) (2026-10-29)


### Features

* **argo:** apps status checks each pinned image against its registry ([#2605](https://github.com/dan-petty/devops-cli/issues/2605)) ([6933005](https://github.com/dan-petty/devops-cli/commit/69330051f515c5c10741fd79d2768bb79c2d60b3)), closes [#1997](https://github.com/dan-petty/devops-cli/issues/1997)
* **k8s:** push the Argo CD notifier App's IDs and key ([#2608](https://github.com/dan-petty/devops-cli/issues/2608)) ([a408dee](https://github.com/dan-petty/devops-cli/commit/a408dee1361e9bd198993edd58712c25ef7c3dee))
* **release:** an urgent fix merges the release pull request ([#2596](https://github.com/dan-petty/devops-cli/issues/2596)) ([20e8ac4](https://github.com/dan-petty/devops-cli/commit/20e8ac46a41f267a7ee052bd829510cc68cb4ad9))
* **roadmap:** a webhook event runs intake of its one issue ([#2607](https://github.com/dan-petty/devops-cli/issues/2607)) ([cf9f02c](https://github.com/dan-petty/devops-cli/commit/cf9f02c2a4fa0051751a783f55548f5c2f52e1de)), closes [#2009](https://github.com/dan-petty/devops-cli/issues/2009)
* **roadmap:** devops roadmap intake-eval scores duplicates ([#2601](https://github.com/dan-petty/devops-cli/issues/2601)) ([22146d6](https://github.com/dan-petty/devops-cli/commit/22146d65d9d3588e4a349a3ced60a682c710c88a))


### Code Refactoring

* **ai:** three in-process caches use cachetools ([#2611](https://github.com/dan-petty/devops-cli/issues/2611)) ([0c30d2a](https://github.com/dan-petty/devops-cli/commit/0c30d2a8c232e558568f056b788fda83d1947aba)), closes [#1993](https://github.com/dan-petty/devops-cli/issues/1993)

## [0.13.2](https://github.com/dan-petty/devops-cli/compare/v0.13.1...v0.13.2) (2026-10-29)


### Performance Improvements

* **valkey:** the caches of a process share one Valkey cache tier ([#2604](https://github.com/dan-petty/devops-cli/issues/2604)) ([c778cde](https://github.com/dan-petty/devops-cli/commit/c778cde87479fdc6a89e4865d454810d6c629591))

## [0.13.1](https://github.com/dan-petty/devops-cli/compare/v0.13.0...v0.13.1) (2026-10-29)


### Bug Fixes

* **roadmap:** import refine at module level to avoid deadlock ([#2535](https://github.com/dan-petty/devops-cli/issues/2535)) ([#2599](https://github.com/dan-petty/devops-cli/issues/2599)) ([3731dff](https://github.com/dan-petty/devops-cli/commit/3731dff0080a40b9e81ddfd928d20454d266f6be))


### Code Refactoring

* **review:** retire the unread review guards file ([#2595](https://github.com/dan-petty/devops-cli/issues/2595)) ([6ae7123](https://github.com/dan-petty/devops-cli/commit/6ae7123d8e94647906d55c5fabe85240204787cd)), closes [#1916](https://github.com/dan-petty/devops-cli/issues/1916)

## [0.13.0](https://github.com/dan-petty/devops-cli/compare/v0.12.0...v0.13.0) (2026-10-29)


### Features

* **gh:** devops gh issues close records the close reason and a comment ([#2575](https://github.com/dan-petty/devops-cli/issues/2575)) ([97ed0ea](https://github.com/dan-petty/devops-cli/commit/97ed0ea9b58a92c1b3ca7b756356228da662826f)), closes [#1658](https://github.com/dan-petty/devops-cli/issues/1658)
* **monitoring:** the ai spend dashboard counts gateway traffic from the gateway's own series, shows failed attempts and names each caller ([#2584](https://github.com/dan-petty/devops-cli/issues/2584)) ([33491ca](https://github.com/dan-petty/devops-cli/commit/33491ca1e6640426258abcf35bf330fde536f2df))
* **roadmap:** refine writes each criterion as an OpenSpec requirement ([#2591](https://github.com/dan-petty/devops-cli/issues/2591)) ([d9a869f](https://github.com/dan-petty/devops-cli/commit/d9a869fda490d8bfd7343ae7b8622fc8cc1aeaa8))
* **sandbox:** sandbox commands take a seccomp profile file ([#2588](https://github.com/dan-petty/devops-cli/issues/2588)) ([46958d4](https://github.com/dan-petty/devops-cli/commit/46958d4b56ce18d3420b6a96d25fa8facbefbdc0))


### Bug Fixes

* **monitoring:** RoadmapServiceGitHubWritesHigh counts a request with no method label as a write, so it fired on 341 reads ([#2583](https://github.com/dan-petty/devops-cli/issues/2583)) ([6dc3aa7](https://github.com/dan-petty/devops-cli/commit/6dc3aa7acae4331c686edd41758717ffa448b7f4)), closes [#2574](https://github.com/dan-petty/devops-cli/issues/2574)


### Performance Improvements

* **ci:** the gate writes no coverage XML, and the clean-up keeps the combined data ([#2582](https://github.com/dan-petty/devops-cli/issues/2582)) ([ae9ebb2](https://github.com/dan-petty/devops-cli/commit/ae9ebb23b2a2da7f7d82c8c587a55ce8036ee275)), closes [#1743](https://github.com/dan-petty/devops-cli/issues/1743)
* **roadmap:** intake's embeddings are cached in a password-protected Valkey in the cluster ([#2578](https://github.com/dan-petty/devops-cli/issues/2578)) ([bfe8a0c](https://github.com/dan-petty/devops-cli/commit/bfe8a0ce6356222c082bc976a7b8ef5f9b161e28))


### Code Refactoring

* **devcontainer:** remove the DEVOPS_CLI_SKIP_TOOL_BOOTSTRAP test switch from product code ([#2580](https://github.com/dan-petty/devops-cli/issues/2580)) ([7e7272e](https://github.com/dan-petty/devops-cli/commit/7e7272e7c19b713a0894bf7c12ec59e6b1d5ad2a))
* **lint:** lazy exports import names under TYPE_CHECKING ([#2590](https://github.com/dan-petty/devops-cli/issues/2590)) ([c96dbfe](https://github.com/dan-petty/devops-cli/commit/c96dbfe326cd24a129b598c72ef57b7ee0b19346)), closes [#2010](https://github.com/dan-petty/devops-cli/issues/2010)

## [0.12.0](https://github.com/dan-petty/devops-cli/compare/v0.11.3...v0.12.0) (2026-10-29)


### Features

* **ai:** constrain structured replies on the openai and claude providers ([#2550](https://github.com/dan-petty/devops-cli/issues/2550)) ([4f7390a](https://github.com/dan-petty/devops-cli/commit/4f7390ac3e34b449e7ef6b4eadfef907c475d5e9))
* **argo:** retire the Helm release records of the charts that Argo CD renders ([#2568](https://github.com/dan-petty/devops-cli/issues/2568)) ([cabfcd4](https://github.com/dan-petty/devops-cli/commit/cabfcd433784100d0e5e437107ff8f32b3537cc3))
* **k8s:** devops k8s tunnel keeps the cloudflared forward to k8s.&lt;domain&gt; running ([#2567](https://github.com/dan-petty/devops-cli/issues/2567)) ([f9493fa](https://github.com/dan-petty/devops-cli/commit/f9493fa48a5e3866192d627f02fb8f508f6069de)), closes [#1641](https://github.com/dan-petty/devops-cli/issues/1641)
* **monitoring:** alert when the otel collector fails to export spans, metric points or log records ([#2565](https://github.com/dan-petty/devops-cli/issues/2565)) ([4fc8ff7](https://github.com/dan-petty/devops-cli/commit/4fc8ff758580e1b8d59a089c97efdd82c5724ee6))
* **telemetry:** the roadmap Service counts its GitHub writes, budget holds, Firecrawl searches and own deliveries, and caps refine's comments on one item ([#2556](https://github.com/dan-petty/devops-cli/issues/2556)) ([9819877](https://github.com/dan-petty/devops-cli/commit/981987792e60b08519ced8bf1c0317a294df432f)), closes [#2475](https://github.com/dan-petty/devops-cli/issues/2475)


### Bug Fixes

* **git:** report a worktree that a run in parallel removed as removed, not a failed reclaim ([#2557](https://github.com/dan-petty/devops-cli/issues/2557)) ([a556984](https://github.com/dan-petty/devops-cli/commit/a556984b700ecc235d421da7d70f61a71728e084)), closes [#2408](https://github.com/dan-petty/devops-cli/issues/2408)
* **k8s:** the devops perimeter opens only the collector's OTLP/HTTP port, 4318 ([#2549](https://github.com/dan-petty/devops-cli/issues/2549)) ([d156ce7](https://github.com/dan-petty/devops-cli/commit/d156ce7e6860140701fd9e88ac33c9565e6dce54))
* **sandbox:** devops sandbox logs reads each line with its stream from a real engine ([#2546](https://github.com/dan-petty/devops-cli/issues/2546)) ([e7216d5](https://github.com/dan-petty/devops-cli/commit/e7216d5f8a0d6cd9677a1cb9ff3e06fd92ec4c6a)), closes [#2520](https://github.com/dan-petty/devops-cli/issues/2520)
* **service:** the webhook route refuses an unsigned or oversized delivery before it reads the body, and a rate limit guards it ([#2553](https://github.com/dan-petty/devops-cli/issues/2553)) ([40efcd4](https://github.com/dan-petty/devops-cli/commit/40efcd4baf6bf9916e00096560bf6538e907e6a3)), closes [#2476](https://github.com/dan-petty/devops-cli/issues/2476)


### Performance Improvements

* **ai:** price a request with one load of the settings ([#2555](https://github.com/dan-petty/devops-cli/issues/2555)) ([5d86538](https://github.com/dan-petty/devops-cli/commit/5d86538a6100414df1aa3bc4f0450010ddb0ff1f)), closes [#1420](https://github.com/dan-petty/devops-cli/issues/1420)


### Code Refactoring

* **config:** a default that backs a settings field is read only through the settings ([#2561](https://github.com/dan-petty/devops-cli/issues/2561)) ([0702d13](https://github.com/dan-petty/devops-cli/commit/0702d13328e746bb288469bd3048024665fe8738))
* **exceptions:** each exception class declares its error_code and exit_code ([#2558](https://github.com/dan-petty/devops-cli/issues/2558)) ([410dece](https://github.com/dan-petty/devops-cli/commit/410dece30f87519df0941eb8587dcbd822efd495))
* **review:** render the review report from one input, outside the orchestrator ([#2563](https://github.com/dan-petty/devops-cli/issues/2563)) ([9e73e6d](https://github.com/dan-petty/devops-cli/commit/9e73e6d0250b57bfb464115e4f7acd753bd03623)), closes [#1008](https://github.com/dan-petty/devops-cli/issues/1008)
* **security:** src has no unreviewed Bandit findings, and the gate scans src at low severity ([#2560](https://github.com/dan-petty/devops-cli/issues/2560)) ([45261dd](https://github.com/dan-petty/devops-cli/commit/45261dde210b03b2ee658b87accaab7037fd7a69)), closes [#1538](https://github.com/dan-petty/devops-cli/issues/1538)
* **security:** the scanners stop looking for mocks, and their tests run on the scanner fake ([#2551](https://github.com/dan-petty/devops-cli/issues/2551)) ([2b7f37a](https://github.com/dan-petty/devops-cli/commit/2b7f37a7c549fa9a6a167ee31024eaa5904846ce))

## [0.11.3](https://github.com/dan-petty/devops-cli/compare/v0.11.2...v0.11.3) (2026-10-28)


### Bug Fixes

* **roadmap:** refine wraps no link in the model's code, and wraps each reference and link that GitHub makes from its text ([#2540](https://github.com/dan-petty/devops-cli/issues/2540)) ([2d38f8d](https://github.com/dan-petty/devops-cli/commit/2d38f8d8ca27cf38f798310d7d40f2869372b16b)), closes [#2525](https://github.com/dan-petty/devops-cli/issues/2525)


### Code Refactoring

* **docker:** DockerEngineService is the Docker engine seam, with an in-memory engine fake and its contract suite ([#2534](https://github.com/dan-petty/devops-cli/issues/2534)) ([1244cbf](https://github.com/dan-petty/devops-cli/commit/1244cbfd5fa0f082c18e6e8cf8a0d0769e3d738e)), closes [#1316](https://github.com/dan-petty/devops-cli/issues/1316)
* **security:** one keyring seam owns the keyring and the Secret Service, with a shared fake and its contract suite ([#2532](https://github.com/dan-petty/devops-cli/issues/2532)) ([866d2cb](https://github.com/dan-petty/devops-cli/commit/866d2cb0cb770057e07bd99fcf8ffbe411383e34)), closes [#1318](https://github.com/dan-petty/devops-cli/issues/1318)
* **telemetry:** OTLP export goes through one exporter seam, and tests read exported spans and metrics from a shared fake ([#2541](https://github.com/dan-petty/devops-cli/issues/2541)) ([8da35e6](https://github.com/dan-petty/devops-cli/commit/8da35e602c43b56a82d0a5b5d7904794a719d4de)), closes [#1319](https://github.com/dan-petty/devops-cli/issues/1319)

## [0.11.2](https://github.com/dan-petty/devops-cli/compare/v0.11.1...v0.11.2) (2026-10-28)


### Bug Fixes

* **service:** the last rate limit of a request holds every worker until its wait ends ([#2529](https://github.com/dan-petty/devops-cli/issues/2529)) ([657b03d](https://github.com/dan-petty/devops-cli/commit/657b03d00786fa2e1909d0ed0ca1d4abf8ac3caa)), closes [#2523](https://github.com/dan-petty/devops-cli/issues/2523)

## [0.11.1](https://github.com/dan-petty/devops-cli/compare/v0.11.0...v0.11.1) (2026-10-28)


### Bug Fixes

* **config:** devops config audit-keys scans each config file that the settings merge ([#2516](https://github.com/dan-petty/devops-cli/issues/2516)) ([57541df](https://github.com/dan-petty/devops-cli/commit/57541df1e04933e0ce6fa5161d1cdaa4280175a4))
* **security:** the osv, internetdb, radar and cloudflare api clients dial through the egress-checked factory at the public level ([#2509](https://github.com/dan-petty/devops-cli/issues/2509)) ([0379f21](https://github.com/dan-petty/devops-cli/commit/0379f21e489bf5204c03e336d17992dbedbe2707))


### Code Refactoring

* **k8s:** KubernetesService is the Kubernetes API seam, with a shared fake cluster and its contract suite ([#2527](https://github.com/dan-petty/devops-cli/issues/2527)) ([0f6b9af](https://github.com/dan-petty/devops-cli/commit/0f6b9af47acb7cd6324a7718fc89580bf66bf12b)), closes [#1315](https://github.com/dan-petty/devops-cli/issues/1315)

## [0.11.0](https://github.com/dan-petty/devops-cli/compare/v0.10.1...v0.11.0) (2026-10-28)


### Features

* **monitoring:** the roadmap Service's identity refusals, failing and stalled jobs, restarts, and GitHub and model request volume raise alerts ([#2496](https://github.com/dan-petty/devops-cli/issues/2496)) ([0137f23](https://github.com/dan-petty/devops-cli/commit/0137f231e910896d8805b527baeae6e0be13e090)), closes [#2472](https://github.com/dan-petty/devops-cli/issues/2472)
* **service:** roadmap-service runs at one replica, and each model call in the cluster is sent at most two times ([#2500](https://github.com/dan-petty/devops-cli/issues/2500)) ([2d32dae](https://github.com/dan-petty/devops-cli/commit/2d32daea17234ef27195f49dc64d2fddf700d478)), closes [#2494](https://github.com/dan-petty/devops-cli/issues/2494)


### Bug Fixes

* **cli:** every command reports a DevOpsCLIError through one exit seam ([#2502](https://github.com/dan-petty/devops-cli/issues/2502)) ([eadd55f](https://github.com/dan-petty/devops-cli/commit/eadd55f1f1caf6d110ac37995e993b806c81f39f)), closes [#2487](https://github.com/dan-petty/devops-cli/issues/2487)
* **github:** pr monitor waits until the checks settle and names every blocker, and pr ready reads the merge-readiness verdict ([#2498](https://github.com/dan-petty/devops-cli/issues/2498)) ([43326ea](https://github.com/dan-petty/devops-cli/commit/43326eadc7cc20e05979f5ab50d0bed2a275648c))
* **k8s:** a pod that does not call the Kubernetes API mounts no service account token ([#2522](https://github.com/dan-petty/devops-cli/issues/2522)) ([305d3ba](https://github.com/dan-petty/devops-cli/commit/305d3ba0f7795b2af8d3ca16d0917cc322ac2a9b))
* **k8s:** the cloudflared tunnel replicas prefer different nodes and keep one up through a drain ([#2499](https://github.com/dan-petty/devops-cli/issues/2499)) ([d4edaf6](https://github.com/dan-petty/devops-cli/commit/d4edaf6fecdf88c40c1e0e781ccee86832901899)), closes [#1023](https://github.com/dan-petty/devops-cli/issues/1023)
* **k8s:** the grafana, prometheus, argo cd and loki clients dial through the egress-checked factory, and their pre-flight address checks go ([#2497](https://github.com/dan-petty/devops-cli/issues/2497)) ([e7ca1d5](https://github.com/dan-petty/devops-cli/commit/e7ca1d52faaf25b085a28bf60c32a59686b70750))
* **monitoring:** the roadmap Service alerts count a series that starts in the hour, and a lane of a new pod can stall ([#2514](https://github.com/dan-petty/devops-cli/issues/2514)) ([c7692b2](https://github.com/dan-petty/devops-cli/commit/c7692b286ed6fa7cb741d4a3af354faaf6f1d14c)), closes [#2505](https://github.com/dan-petty/devops-cli/issues/2505)
* **review:** a review's scanners leave out the rules that never gave a valid finding here ([#2508](https://github.com/dan-petty/devops-cli/issues/2508)) ([fe953ac](https://github.com/dan-petty/devops-cli/commit/fe953ac43788767f6563368be35d7ed421b53d1f))
* **roadmap:** a refine round leaves an outside account issue to a person, and refine neutralizes comment openers, www links and cross-repository references ([#2507](https://github.com/dan-petty/devops-cli/issues/2507)) ([e6230dc](https://github.com/dan-petty/devops-cli/commit/e6230dcf6a6299776d9c6feca56422ac8615468e)), closes [#2478](https://github.com/dan-petty/devops-cli/issues/2478)
* **sandbox:** the metrics scrape and the whitelist NetworkPolicy resolve each host one time, through the egress check ([#2521](https://github.com/dan-petty/devops-cli/issues/2521)) ([7c01426](https://github.com/dan-petty/devops-cli/commit/7c0142691056ac085d5de2e889b46848b6c4bee5))
* **security:** the subprocess environment guard refuses the zsh and interpreter keys that make a child run code ([#2510](https://github.com/dan-petty/devops-cli/issues/2510)) ([459621a](https://github.com/dan-petty/devops-cli/commit/459621a6b7fc8151d0c2289943ea3e0fd495aa25))
* **service:** a restart keeps the halt, the budget window and the failure ledger, and a rate limit or a suspended installation stops every worker ([#2515](https://github.com/dan-petty/devops-cli/issues/2515)) ([3630de1](https://github.com/dan-petty/devops-cli/commit/3630de162aea9a63b69ebe11cd8f93d389f60d12)), closes [#2474](https://github.com/dan-petty/devops-cli/issues/2474)


### Code Refactoring

* **config:** settings resolve in one declared order through pydantic-settings sources ([#2518](https://github.com/dan-petty/devops-cli/issues/2518)) ([6a5447a](https://github.com/dan-petty/devops-cli/commit/6a5447a5cdccd105196d52f6327dfad1daa5f445)), closes [#2445](https://github.com/dan-petty/devops-cli/issues/2445)

## [0.10.1](https://github.com/dan-petty/devops-cli/compare/v0.10.0...v0.10.1) (2026-10-28)


### Bug Fixes

* **ai:** a reply names its server by the origin of the URL called, so a password in an AI URL stays out of every record ([#2488](https://github.com/dan-petty/devops-cli/issues/2488)) ([3ec083f](https://github.com/dan-petty/devops-cli/commit/3ec083f7ace66ba7cfaa44c4806be7806e1958b0)), closes [#1110](https://github.com/dan-petty/devops-cli/issues/1110)
* **ai:** the AI service clients dial through the egress-checked factory and check the address at the connect ([#2484](https://github.com/dan-petty/devops-cli/issues/2484)) ([08d70ca](https://github.com/dan-petty/devops-cli/commit/08d70ca6e2fa70254f333f79201c5897072d027b))


### Code Refactoring

* **config:** each setting declares its variable on its settings field, and the option, variable and secret registries are derived from it ([#2466](https://github.com/dan-petty/devops-cli/issues/2466)) ([daaffc6](https://github.com/dan-petty/devops-cli/commit/daaffc62f8ca99b96949f2c13e9dcdd5bc781351))

## [0.10.0](https://github.com/dan-petty/devops-cli/compare/v0.9.0...v0.10.0) (2026-10-28)


### Features

* **review:** devops review intake hands the findings of a session on merged code to roadmap intake ([#2455](https://github.com/dan-petty/devops-cli/issues/2455)) ([a5c7b82](https://github.com/dan-petty/devops-cli/commit/a5c7b82c8725fd5d4d389ecbf2075db7d8fc36e1))
* **security:** devops k8s audit runs Popeye in the tool sandbox with a kube-api network profile that only reads the API server ([#2467](https://github.com/dan-petty/devops-cli/issues/2467)) ([e02c3fb](https://github.com/dan-petty/devops-cli/commit/e02c3fb0332dd5917fc5c79890269f252c3ce2dc))
* **security:** the App's installation tokens carry only the permissions the roadmap jobs use ([#2482](https://github.com/dan-petty/devops-cli/issues/2482)) ([9599ef2](https://github.com/dan-petty/devops-cli/commit/9599ef2826447facf12ae65c9d76152436b4e39d)), closes [#2473](https://github.com/dan-petty/devops-cli/issues/2473)


### Bug Fixes

* **config:** a config file that is not valid YAML stops the load with an error that quotes none of its text ([#2468](https://github.com/dan-petty/devops-cli/issues/2468)) ([91fe5dc](https://github.com/dan-petty/devops-cli/commit/91fe5dce0eea97c67e0b86f1348772a4e6d66924))
* **config:** config set reports an unknown key as unknown, not as a key that needs a value ([#2465](https://github.com/dan-petty/devops-cli/issues/2465)) ([8b650a6](https://github.com/dan-petty/devops-cli/commit/8b650a649d02134c8816f2f976c4ae7943adeef8))
* **devcontainer:** run the checkout's devops in devcontainer terminals ([#2460](https://github.com/dan-petty/devops-cli/issues/2460)) ([abd2d41](https://github.com/dan-petty/devops-cli/commit/abd2d41bccfe28d60297af7fb7520369b51e5723))
* **k8s:** loki runs from the grafana-community chart on loki 3.7.9, out of reach of CVE-2026-21729 ([#2470](https://github.com/dan-petty/devops-cli/issues/2470)) ([96c50c9](https://github.com/dan-petty/devops-cli/commit/96c50c989961242125ed59e133d87461be864f29))
* **security:** a credential keyword at the end of a line no longer masks the first word of the next line ([#2461](https://github.com/dan-petty/devops-cli/issues/2461)) ([b754a73](https://github.com/dan-petty/devops-cli/commit/b754a73a775953331c7aec2f1d8e9a857462677e))
* **security:** a credential value is masked also when the next line starts with a parenthesis ([#2477](https://github.com/dan-petty/devops-cli/issues/2477)) ([ece25ca](https://github.com/dan-petty/devops-cli/commit/ece25ca5ee6e01eaa4b3779693d2f85ac7be10cf)), closes [#2471](https://github.com/dan-petty/devops-cli/issues/2471)
* **security:** pin kubeconform and replace Checkov with Trivy's misconfiguration scan ([#2464](https://github.com/dan-petty/devops-cli/issues/2464)) ([960e357](https://github.com/dan-petty/devops-cli/commit/960e3573da1f45b342fd4d85a5cdcfefbae608f6))
* **security:** refuse GCONV_PATH, SHELLOPTS, BASHOPTS and PS4 from a caller, and archive the merged security changes ([#2453](https://github.com/dan-petty/devops-cli/issues/2453)) ([1f9231d](https://github.com/dan-petty/devops-cli/commit/1f9231d24978c934b37496c81d209620852df217))


### Code Refactoring

* **ai:** chat_structured is the one structured-output path ([#2452](https://github.com/dan-petty/devops-cli/issues/2452)) ([3509732](https://github.com/dan-petty/devops-cli/commit/350973281ac8be81f9fadc2a23df86616576798c))
* **github:** pr check-readiness reads one merge-readiness verdict from github/ ([#2456](https://github.com/dan-petty/devops-cli/issues/2456)) ([16442c4](https://github.com/dan-petty/devops-cli/commit/16442c4ebb6ce1273396d5fd4f86830fdfcbeb1a))

## [0.9.0](https://github.com/dan-petty/devops-cli/compare/v0.8.3...v0.9.0) (2026-10-28)


### Features

* **ai:** observe the Ollama slot wait by priority and chart its p95 ([#2404](https://github.com/dan-petty/devops-cli/issues/2404)) ([ffeeda4](https://github.com/dan-petty/devops-cli/commit/ffeeda4514b5a1c2934c6811601a74373d3a1666))
* **github:** send GitHub request, throttle and GraphQL point metrics, and show them on the devops-cli dashboard ([#2406](https://github.com/dan-petty/devops-cli/issues/2406)) ([bded64b](https://github.com/dan-petty/devops-cli/commit/bded64b22c9c1bb3c6f87cae2fd255c50347a619))
* **k8s:** gpu row panels for clock-event reasons, power against the enforced limit and pcie throughput ([#2409](https://github.com/dan-petty/devops-cli/issues/2409)) ([21f023c](https://github.com/dan-petty/devops-cli/commit/21f023cb4b0bd700b20fc05d46deb79492c893d1)), closes [#821](https://github.com/dan-petty/devops-cli/issues/821)
* **review:** a review session records its head commit and clean tree, and says whether it is on merged code ([#2434](https://github.com/dan-petty/devops-cli/issues/2434)) ([8b4ed46](https://github.com/dan-petty/devops-cli/commit/8b4ed46eac4e0efc50889a066909f6896bbe1fcd))
* **review:** an issue filed from a review finding carries its fingerprint, and the review leaves out a finding that an issue already carries ([#2428](https://github.com/dan-petty/devops-cli/issues/2428)) ([acace03](https://github.com/dan-petty/devops-cli/commit/acace0343d15369eca9995a7bdbef54781a9bb16))
* **review:** the feedback export counts each review subject once and keeps every human verdict ([#2417](https://github.com/dan-petty/devops-cli/issues/2417)) ([73d1807](https://github.com/dan-petty/devops-cli/commit/73d180770396c73d6a4c990bbbe035d084b5f76d))
* **roadmap:** act as GitHub App devops-roadmap instead of a machine account ([#2411](https://github.com/dan-petty/devops-cli/issues/2411)) ([d739a47](https://github.com/dan-petty/devops-cli/commit/d739a472dcfc7c8394513e4afcaad359b5a0fbd4)), closes [#1647](https://github.com/dan-petty/devops-cli/issues/1647)
* **roadmap:** labels and milestones hold each item's status, priority, value and effort, and no roadmap job reads or writes the project board ([#2435](https://github.com/dan-petty/devops-cli/issues/2435)) ([84f02a1](https://github.com/dan-petty/devops-cli/commit/84f02a1a523970fdd921520cac7d4df4a58769d3)), closes [#2399](https://github.com/dan-petty/devops-cli/issues/2399)
* **roadmap:** refine investigates open questions with code and web tools and decides design questions by the best practice ([#2410](https://github.com/dan-petty/devops-cli/issues/2410)) ([890e228](https://github.com/dan-petty/devops-cli/commit/890e228e99e5dfe2c52d6c2d81e91fa829ad15b0)), closes [#2398](https://github.com/dan-petty/devops-cli/issues/2398)
* **telemetry:** count embedding cache lookups and send every metric through a declared instrument ([#2416](https://github.com/dan-petty/devops-cli/issues/2416)) ([19412fa](https://github.com/dan-petty/devops-cli/commit/19412fa931476f94afebef7b2229be8379b24f88))


### Bug Fixes

* **git:** ignore missing files when measuring directory size during reclaim ([#2438](https://github.com/dan-petty/devops-cli/issues/2438)) ([4226904](https://github.com/dan-petty/devops-cli/commit/4226904e21d18adfbe4b4516c3be09391634c18e))
* **security:** scan all namespaces with Popeye when no namespace is given ([#2436](https://github.com/dan-petty/devops-cli/issues/2436)) ([4d5f789](https://github.com/dan-petty/devops-cli/commit/4d5f78937f24fcb459c9c51ae570fb8711c908fa))
* **security:** scan_uv_audit runs a uv audit adapter that audits the lockfile as it is ([#2446](https://github.com/dan-petty/devops-cli/issues/2446)) ([0b2d005](https://github.com/dan-petty/devops-cli/commit/0b2d00564295e3b0daa5b7ab4da54ed2b59bd445)), closes [#2106](https://github.com/dan-petty/devops-cli/issues/2106)

## [0.8.3](https://github.com/dan-petty/devops-cli/compare/v0.8.2...v0.8.3) (2026-10-28)


### Bug Fixes

* **ai:** the gateway sweep's URL error names no credential ([#2400](https://github.com/dan-petty/devops-cli/issues/2400)) ([2e6f1fd](https://github.com/dan-petty/devops-cli/commit/2e6f1fdb3bcbfaecc882f72c47607d59f3f9ad83)), closes [#909](https://github.com/dan-petty/devops-cli/issues/909)
* **config:** exit 1 when audit-keys finds a plaintext secret ([#2401](https://github.com/dan-petty/devops-cli/issues/2401)) ([ad0114f](https://github.com/dan-petty/devops-cli/commit/ad0114f39ab61ec6630109f0c658ad8eea13fadf)), closes [#1469](https://github.com/dan-petty/devops-cli/issues/1469)
* **security:** drop the Go ignores that the pinned gh build does not need ([#2402](https://github.com/dan-petty/devops-cli/issues/2402)) ([6052083](https://github.com/dan-petty/devops-cli/commit/605208329b8f29e1f35254e9f62a12048df13974)), closes [#1492](https://github.com/dan-petty/devops-cli/issues/1492)
* **security:** refuse every loader and shell key that loads code into a child ([#2405](https://github.com/dan-petty/devops-cli/issues/2405)) ([86d5bce](https://github.com/dan-petty/devops-cli/commit/86d5bce9971664d6247e5665eacb5e5d1e380b5e)), closes [#2205](https://github.com/dan-petty/devops-cli/issues/2205)

## [0.8.2](https://github.com/dan-petty/devops-cli/compare/v0.8.1...v0.8.2) (2026-10-28)


### Bug Fixes

* **github:** a failed milestone patch leaves the created issue without a milestone, the board-less triage audit reports no missing priority, and review threads read every comment page ([#2158](https://github.com/dan-petty/devops-cli/issues/2158)) ([#2394](https://github.com/dan-petty/devops-cli/issues/2394)) ([d509dba](https://github.com/dan-petty/devops-cli/commit/d509dba7bf6f37dffe17fe482592946a5310fd32))
* **k8s:** bound prompt cache and set memory limit on ollama-64gib tier ([#2391](https://github.com/dan-petty/devops-cli/issues/2391)) ([69636b6](https://github.com/dan-petty/devops-cli/commit/69636b6c7b754c7d8aa222c2d2d7d4cf55901772))
* **k8s:** remove IQ3_S gateway deployment from qwen3.8 and chat groups ([#2393](https://github.com/dan-petty/devops-cli/issues/2393)) ([0b76871](https://github.com/dan-petty/devops-cli/commit/0b76871b859a0fb20ac41d297253b41bc7890f30))

## [0.8.1](https://github.com/dan-petty/devops-cli/compare/v0.8.0...v0.8.1) (2026-10-27)


### Bug Fixes

* **devcontainer:** provide reset remedy on wrong keyring password ([#2390](https://github.com/dan-petty/devops-cli/issues/2390)) ([5031b1d](https://github.com/dan-petty/devops-cli/commit/5031b1d8751028962a904ade03cd452c6e8cefab))
* **k8s:** the --stack help of deploy-stack names every stack that the command accepts ([#2388](https://github.com/dan-petty/devops-cli/issues/2388)) ([69fe9b3](https://github.com/dan-petty/devops-cli/commit/69fe9b38345713adab90d6ba4fa3782e1a0c4db3))
* **monitoring:** evaluate log or metric volume disk low alert while a pod moves ([#2387](https://github.com/dan-petty/devops-cli/issues/2387)) ([7b381ea](https://github.com/dan-petty/devops-cli/commit/7b381ea168177a8e938b28c0f3b17712542fb096))

## [0.8.0](https://github.com/dan-petty/devops-cli/compare/v0.7.4...v0.8.0) (2026-10-27)


### Features

* **github:** devops gh issues view shows one issue ([#2374](https://github.com/dan-petty/devops-cli/issues/2374)) ([63be7ed](https://github.com/dan-petty/devops-cli/commit/63be7edbd54fea1e0ad55813f8b2b471695df892)), closes [#2361](https://github.com/dan-petty/devops-cli/issues/2361)
* **repos:** make devops repos worktrees add remove merged worktrees first ([#2351](https://github.com/dan-petty/devops-cli/issues/2351)) ([6d3a18a](https://github.com/dan-petty/devops-cli/commit/6d3a18a52a99445a605b6304d3ea69de6aab7407)), closes [#2338](https://github.com/dan-petty/devops-cli/issues/2338)


### Bug Fixes

* **k8s:** devops k8s configure-urls saves a run that changes only the task gateway urls ([#2384](https://github.com/dan-petty/devops-cli/issues/2384)) ([1a7e7c7](https://github.com/dan-petty/devops-cli/commit/1a7e7c786c60e3abd213802f24f23a841fc7cacd))
* **k8s:** exit non-zero when kube-linter is unavailable or reports findings ([#2386](https://github.com/dan-petty/devops-cli/issues/2386)) ([31c5a0b](https://github.com/dan-petty/devops-cli/commit/31c5a0b4d8dad571fade56144fe3d11287fba6c2)), closes [#2095](https://github.com/dan-petty/devops-cli/issues/2095)
* **scan:** serialize status and reason in JSON and YAML scan output ([#2385](https://github.com/dan-petty/devops-cli/issues/2385)) ([d594b55](https://github.com/dan-petty/devops-cli/commit/d594b55213c3a8d118f43cc09d98045f39fc0d3f))

## [0.7.4](https://github.com/dan-petty/devops-cli/compare/v0.7.3...v0.7.4) (2026-10-27)


### Bug Fixes

* **ai:** chat calls stream their reply, and the gateway keeps the stream open past the 125 s edge timeout ([#2379](https://github.com/dan-petty/devops-cli/issues/2379)) ([0abf552](https://github.com/dan-petty/devops-cli/commit/0abf552a0ab7b587abffcc5ade6c49407aca5e2d)), closes [#2365](https://github.com/dan-petty/devops-cli/issues/2365)
* **ai:** the devops ai failover help says that the gateway failover records a route, not that it reroutes requests ([#2376](https://github.com/dan-petty/devops-cli/issues/2376)) ([6560b93](https://github.com/dan-petty/devops-cli/commit/6560b93169922ade3a6694fe914bdcbe5c9adad1)), closes [#2079](https://github.com/dan-petty/devops-cli/issues/2079)
* **docs:** add home page, remove raw markdown publishing, and check links ([#2070](https://github.com/dan-petty/devops-cli/issues/2070)) ([#2372](https://github.com/dan-petty/devops-cli/issues/2372)) ([7f9321c](https://github.com/dan-petty/devops-cli/commit/7f9321c55734e3939005706b274c7db9757c2b0a))
* **llm:** pass num_ctx with direct ollama embedding requests ([#2378](https://github.com/dan-petty/devops-cli/issues/2378)) ([ff47504](https://github.com/dan-petty/devops-cli/commit/ff475047a19fc30d0b22a97327311505d52d61bd)), closes [#2089](https://github.com/dan-petty/devops-cli/issues/2089)
* **roadmap:** intake's reply schema limits each fixed field to its values, so the model cannot leave type empty ([#2380](https://github.com/dan-petty/devops-cli/issues/2380)) ([b9220b1](https://github.com/dan-petty/devops-cli/commit/b9220b1ad4893fa19f47f85f15b7586c3be42c93)), closes [#2370](https://github.com/dan-petty/devops-cli/issues/2370)
* **telemetry:** a gateway inference span names the deployment model that served the call as gen_ai.response.model ([#2381](https://github.com/dan-petty/devops-cli/issues/2381)) ([78dbd1d](https://github.com/dan-petty/devops-cli/commit/78dbd1d0776799385b364db278476b72e92eb5ff))


### Performance Improvements

* **ci:** lower the coverage floor to 85% and fail a pull request below 90% on its changed lines ([#2375](https://github.com/dan-petty/devops-cli/issues/2375)) ([9f97c14](https://github.com/dan-petty/devops-cli/commit/9f97c14fe6ae1a37965a00835b1388f83d4c8420))

## [0.7.3](https://github.com/dan-petty/devops-cli/compare/v0.7.2...v0.7.3) (2026-10-27)


### Bug Fixes

* **ai:** a saved gateway route table keeps only failover state, so a changed default route reaches every machine ([#2364](https://github.com/dan-petty/devops-cli/issues/2364)) ([8317526](https://github.com/dan-petty/devops-cli/commit/8317526e29a0f94c9d39f56fddb98a08c422d6af))
* **k8s:** delete unused portkey routing configmap ([#2363](https://github.com/dan-petty/devops-cli/issues/2363)) ([15bd601](https://github.com/dan-petty/devops-cli/commit/15bd6014d544fda76e8e87c40e726f7fffa9f8d6))
* **telemetry:** export created timestamps for cluster job counters ([#2039](https://github.com/dan-petty/devops-cli/issues/2039)) ([#2366](https://github.com/dan-petty/devops-cli/issues/2366)) ([cc34caa](https://github.com/dan-petty/devops-cli/commit/cc34caa444c0b0f5bfff0b77dbbfe5c02338691f))

## [0.7.2](https://github.com/dan-petty/devops-cli/compare/v0.7.1...v0.7.2) (2026-10-27)


### Bug Fixes

* **k8s:** guard valkey URL construction and pin configure-urls valkey scheme ([#2359](https://github.com/dan-petty/devops-cli/issues/2359)) ([b369d9a](https://github.com/dan-petty/devops-cli/commit/b369d9a502e8459dd817246ba2cc8f0c3a4f03fe)), closes [#1990](https://github.com/dan-petty/devops-cli/issues/1990)
* **k8s:** spread embedding batches over both order 1 tiers ([#2360](https://github.com/dan-petty/devops-cli/issues/2360)) ([b0f58ac](https://github.com/dan-petty/devops-cli/commit/b0f58acaf517339515bf90ff45e00ce78ce00f48))

## [0.7.1](https://github.com/dan-petty/devops-cli/compare/v0.7.0...v0.7.1) (2026-10-27)


### Bug Fixes

* **ci:** replay fail-to-pass tests in a git worktree of the base ([#2353](https://github.com/dan-petty/devops-cli/issues/2353)) ([5194d60](https://github.com/dan-petty/devops-cli/commit/5194d60092d0fba7a6b3459d8162cda664cc900d))
* **github:** a rate-limit check for another host leaves the github.com quotas unchanged ([#2357](https://github.com/dan-petty/devops-cli/issues/2357)) ([5d37762](https://github.com/dan-petty/devops-cli/commit/5d37762f0981bc53707c772ff7e2b3294fad8fa7))
* **github:** the defect classifier records a lesson in the document that owns it, not in AGENTS.md ([#2358](https://github.com/dan-petty/devops-cli/issues/2358)) ([a47167c](https://github.com/dan-petty/devops-cli/commit/a47167c632c112b56e9a7babca6240dcbe129019))
* **k8s:** create the Grafana token before it revokes the old ones ([#2352](https://github.com/dan-petty/devops-cli/issues/2352)) ([f9c7ef5](https://github.com/dan-petty/devops-cli/commit/f9c7ef515cbd393f434fba8bb869b1b2d9e00c4c))
* **service:** stop every roadmap job on a refused identity and keep GitHub requests under an hourly budget ([#2354](https://github.com/dan-petty/devops-cli/issues/2354)) ([0f00e96](https://github.com/dan-petty/devops-cli/commit/0f00e96ab56ad0d9893e3483eb1ab2ffca986b59))

## [0.7.0](https://github.com/dan-petty/devops-cli/compare/v0.6.5...v0.7.0) (2026-10-27)


### Features

* **ci:** limit how many CPU-heavy gates run at once on one host ([#2339](https://github.com/dan-petty/devops-cli/issues/2339)) ([115d1c1](https://github.com/dan-petty/devops-cli/commit/115d1c1caa1f3719b1659043cff06443b19a8ef3)), closes [#2336](https://github.com/dan-petty/devops-cli/issues/2336)
* **ci:** make devops ci wait for a gate slot before a CPU-heavy check ([#2343](https://github.com/dan-petty/devops-cli/issues/2343)) ([518db63](https://github.com/dan-petty/devops-cli/commit/518db636ad892de9bff654e9869705667127ea0f)), closes [#2336](https://github.com/dan-petty/devops-cli/issues/2336)
* **devcontainer:** onboard Kilo Code with a kilo.jsonc that exposes the devops-cli MCP server ([#2332](https://github.com/dan-petty/devops-cli/issues/2332)) ([3a6189e](https://github.com/dan-petty/devops-cli/commit/3a6189eab951f47d6572dd31ec56039afa45400c))
* **openspec:** commit the OpenSpec skills for Kilo Code ([#2334](https://github.com/dan-petty/devops-cli/issues/2334)) ([9b4a824](https://github.com/dan-petty/devops-cli/commit/9b4a824d50b890b2201ae6797a3a90ec25018f0f)), closes [#2333](https://github.com/dan-petty/devops-cli/issues/2333)
* **repos:** add devops repos worktrees add that refuses a held issue ([#2348](https://github.com/dan-petty/devops-cli/issues/2348)) ([a3b164d](https://github.com/dan-petty/devops-cli/commit/a3b164de872213b4b9aad194b68d0cdad3b730cc)), closes [#2337](https://github.com/dan-petty/devops-cli/issues/2337)


### Bug Fixes

* **deps:** upgrade dnspython to fix GHSA-45c3-73f7-pv4m ([#2350](https://github.com/dan-petty/devops-cli/issues/2350)) ([f50459d](https://github.com/dan-petty/devops-cli/commit/f50459deeecab81429c9ab06d84619d65fbba280))
* **k8s:** k8s apply renders the preview under --dry-run and starts no child process ([#2328](https://github.com/dan-petty/devops-cli/issues/2328)) ([16e26b0](https://github.com/dan-petty/devops-cli/commit/16e26b051250bb31237bae46d67ecd0dcb6607a9)), closes [#2312](https://github.com/dan-petty/devops-cli/issues/2312)
* **k8s:** name the keyring entry when the Grafana admin password is missing ([#2335](https://github.com/dan-petty/devops-cli/issues/2335)) ([f9dcc79](https://github.com/dan-petty/devops-cli/commit/f9dcc790698ed7f1dd209d96207263d8f34a424d))
* **repos:** worktrees prune removes only worktrees of merged pull requests ([#2342](https://github.com/dan-petty/devops-cli/issues/2342)) ([23d864d](https://github.com/dan-petty/devops-cli/commit/23d864d38fa1a040fbd021f6b9e9cbe1e19ac453)), closes [#2341](https://github.com/dan-petty/devops-cli/issues/2341)
* **scan:** keep scan progress off stdout when the output format is json ([#2331](https://github.com/dan-petty/devops-cli/issues/2331)) ([1b17048](https://github.com/dan-petty/devops-cli/commit/1b17048ba119f68b6d8f4d709865cb9ef7e8c010)), closes [#2216](https://github.com/dan-petty/devops-cli/issues/2216)

## [0.6.5](https://github.com/dan-petty/devops-cli/compare/v0.6.4...v0.6.5) (2026-10-26)


### Bug Fixes

* **ai:** analyze pr previews under --dry-run and contacts no service ([#2327](https://github.com/dan-petty/devops-cli/issues/2327)) ([c402b6d](https://github.com/dan-petty/devops-cli/commit/c402b6d67ecbee2df4a83681da03253d0ec17d04))
* **dashboard:** reject unknown tab option values and remove refresh_all ([#2310](https://github.com/dan-petty/devops-cli/issues/2310)) ([27f8c60](https://github.com/dan-petty/devops-cli/commit/27f8c60d3b66c985e98ca6d42a23fd16fba9462e)), closes [#1904](https://github.com/dan-petty/devops-cli/issues/1904)
* **deps:** renovate updates the image tags in k8s/ manifests ([#2325](https://github.com/dan-petty/devops-cli/issues/2325)) ([b0ebce0](https://github.com/dan-petty/devops-cli/commit/b0ebce0a343b1fd5b705fa6d57c3dce20e598e0a))
* **devcontainer:** isolate image build metadata from workspace settings ([#2309](https://github.com/dan-petty/devops-cli/issues/2309)) ([7672c71](https://github.com/dan-petty/devops-cli/commit/7672c7151a7b2eba9f455582a641f265450d2603))
* **output:** remove duplicated check marks from success messages ([#2313](https://github.com/dan-petty/devops-cli/issues/2313)) ([db7c3c4](https://github.com/dan-petty/devops-cli/commit/db7c3c488a058053f7acb0d4f48002f2bab2b500))
* **review:** record coverage gaps on base read failures and accept empty diffs ([#2326](https://github.com/dan-petty/devops-cli/issues/2326)) ([a307ac0](https://github.com/dan-petty/devops-cli/commit/a307ac08be6e17881361697e86c9fd0167cde794))
* **roadmap:** the roadmap runs on a rebuilt board, because GitHub refuses to add 149 issues to board 2 ([#2320](https://github.com/dan-petty/devops-cli/issues/2320)) ([48c78ca](https://github.com/dan-petty/devops-cli/commit/48c78ca94dcb5ef557482da4f7711266d31a7673))
* **security:** cloudflared 2026.10.4 replaces 2026.9.3, which trusts eight compromised eMudhra certificates ([#2324](https://github.com/dan-petty/devops-cli/issues/2324)) ([e6750be](https://github.com/dan-petty/devops-cli/commit/e6750bee2ebdb9ada41b950a6e9a35dd5c392433))
* **security:** prevent directory traversal in response cache and isolate storage ([#2321](https://github.com/dan-petty/devops-cli/issues/2321)) ([1967695](https://github.com/dan-petty/devops-cli/commit/19676954d486853cd1c83489f16ecafe7a9ee8e0))
* **telemetry:** send project gauges through OTLP only ([#2288](https://github.com/dan-petty/devops-cli/issues/2288)) ([#2315](https://github.com/dan-petty/devops-cli/issues/2315)) ([aeaa52e](https://github.com/dan-petty/devops-cli/commit/aeaa52e5b1362e21aa08722c0a947d4ca494acb2))

## [0.6.4](https://github.com/dan-petty/devops-cli/compare/v0.6.3...v0.6.4) (2026-10-26)


### Bug Fixes

* **devcontainer:** report a developer tool's failed installer download as a failure ([#2304](https://github.com/dan-petty/devops-cli/issues/2304)) ([6ca95c1](https://github.com/dan-petty/devops-cli/commit/6ca95c152453032254245dcd44121d90128779ec))
* **k8s:** network policy peers name only namespaces that exist ([#1656](https://github.com/dan-petty/devops-cli/issues/1656)) ([#2302](https://github.com/dan-petty/devops-cli/issues/2302)) ([c77b6e3](https://github.com/dan-petty/devops-cli/commit/c77b6e396480495bad19b7a652f92504f63bf9a9))
* **k8s:** skip post-Helm deletes whose CRD is not installed ([#2307](https://github.com/dan-petty/devops-cli/issues/2307)) ([fe01b30](https://github.com/dan-petty/devops-cli/commit/fe01b30d0e29d6ae348dd86561005bb668fbed44)), closes [#1818](https://github.com/dan-petty/devops-cli/issues/1818)
* **k8s:** warn on kubectl and kubelet version skew in doctor and deploy-stack ([#2306](https://github.com/dan-petty/devops-cli/issues/2306)) ([001a7af](https://github.com/dan-petty/devops-cli/commit/001a7af8981b9dbe702828fdc9381744a4aa9911)), closes [#1640](https://github.com/dan-petty/devops-cli/issues/1640)
* **review:** do not cache rejected review plan replies ([#1810](https://github.com/dan-petty/devops-cli/issues/1810)) ([#2308](https://github.com/dan-petty/devops-cli/issues/2308)) ([aece067](https://github.com/dan-petty/devops-cli/commit/aece067ac6610b68bfe58c8a0de418c03e94519a))


### Performance Improvements

* **ci:** the Static Analysis job runs Bandit once ([#2305](https://github.com/dan-petty/devops-cli/issues/2305)) ([9cca449](https://github.com/dan-petty/devops-cli/commit/9cca449ac5ca6953fe2d150beb1efdf99f08813c)), closes [#1746](https://github.com/dan-petty/devops-cli/issues/1746)

## [0.6.3](https://github.com/dan-petty/devops-cli/compare/v0.6.2...v0.6.3) (2026-10-26)


### Bug Fixes

* **github:** devops gh rate-limit reads only the free /rate_limit endpoint ([#2300](https://github.com/dan-petty/devops-cli/issues/2300)) ([706e386](https://github.com/dan-petty/devops-cli/commit/706e38605387bdb98a773bf2ba48c566d4f215d2)), closes [#1441](https://github.com/dan-petty/devops-cli/issues/1441)
* **github:** the label taxonomy metrics count every open issue across all pages and no pull requests ([#2298](https://github.com/dan-petty/devops-cli/issues/2298)) ([f5cd022](https://github.com/dan-petty/devops-cli/commit/f5cd02270be22002c10489d99fe8801a2ef39359))
* **infra:** cloudflare access sync reads every page of applications and policies and retries rate-limited requests ([#2296](https://github.com/dan-petty/devops-cli/issues/2296)) ([a86aa4b](https://github.com/dan-petty/devops-cli/commit/a86aa4bd7061150ffe8e4003d33eaca7f463b7b8))
* **review:** the review dry run shows the request the model client would send, built by that client ([#2291](https://github.com/dan-petty/devops-cli/issues/2291)) ([9383fd5](https://github.com/dan-petty/devops-cli/commit/9383fd5f0ad17f609fac334eaf4b91a0cb415f8b))
* **security:** devops scan sbom is produced by trivy's cyclonedx and spdx writers ([#2301](https://github.com/dan-petty/devops-cli/issues/2301)) ([d5e47ff](https://github.com/dan-petty/devops-cli/commit/d5e47ffb151f4ceeb82aee761ee5ce08a9cae112))
* **terraform:** drift reads state through tofu show -json, so encrypted state and module resources are no longer misreported ([#2297](https://github.com/dan-petty/devops-cli/issues/2297)) ([169859a](https://github.com/dan-petty/devops-cli/commit/169859ad88aadba6e8c4ef1d8296d5bd3eb56e7f))

## [0.6.2](https://github.com/dan-petty/devops-cli/compare/v0.6.1...v0.6.2) (2026-10-26)


### Bug Fixes

* **ai:** the claude provider sends what current Claude models accept, built by the anthropic SDK ([#2285](https://github.com/dan-petty/devops-cli/issues/2285)) ([59471a4](https://github.com/dan-petty/devops-cli/commit/59471a48278a1d16f9e1840a66c62c6a21189d7a))
* **ai:** the openai provider without ai.api_base_url calls the OpenAI API's /v1 routes, built by the openai SDK ([#2286](https://github.com/dan-petty/devops-cli/issues/2286)) ([a7dd605](https://github.com/dan-petty/devops-cli/commit/a7dd605e2d6946f2554dd88b441f1352d77d8ad2)), closes [#1427](https://github.com/dan-petty/devops-cli/issues/1427)
* **ci:** pin ty in the dev group so a new release cannot fail uv check on main ([#2284](https://github.com/dan-petty/devops-cli/issues/2284)) ([3936fe6](https://github.com/dan-petty/devops-cli/commit/3936fe6ed4fab934b4a7f9c6f173e52585b76f99)), closes [#2281](https://github.com/dan-petty/devops-cli/issues/2281)
* **security:** query documented radar api with token and mark failed lookups unverified ([#2289](https://github.com/dan-petty/devops-cli/issues/2289)) ([c52af09](https://github.com/dan-petty/devops-cli/commit/c52af092d021e342b492063df92587e9592aedc0))
* **telemetry:** the project items gauge counts the items of the project board by milestone, state, type and priority ([#2290](https://github.com/dan-petty/devops-cli/issues/2290)) ([853296c](https://github.com/dan-petty/devops-cli/commit/853296c393b1ed6954937e211c69762a06fa1059))

## [0.6.1](https://github.com/dan-petty/devops-cli/compare/v0.6.0...v0.6.1) (2026-10-26)


### Bug Fixes

* **ai:** the rag index keeps each project's chunks apart, deletes a removed file's points before forgetting it, and refills a project its collection lost ([#2283](https://github.com/dan-petty/devops-cli/issues/2283)) ([ad7c38b](https://github.com/dan-petty/devops-cli/commit/ad7c38b1ede444477af0c4f3a0f09615b0f40b18))
* **cli:** repos sync and branches sync report a failed fetch or pull instead of printing success ([#2276](https://github.com/dan-petty/devops-cli/issues/2276)) ([bf72be1](https://github.com/dan-petty/devops-cli/commit/bf72be1b9fe9064abac361e8f0b0f39b372c0d78))
* **github:** pace GraphQL porcelain commands against graphql quota ([#2280](https://github.com/dan-petty/devops-cli/issues/2280)) ([7f1145a](https://github.com/dan-petty/devops-cli/commit/7f1145a4971391f7f0b3b8545bbf59fa4907a243)), closes [#1415](https://github.com/dan-petty/devops-cli/issues/1415)
* **roadmap:** intake keeps the fields a person set on a card added during its planning ([#2278](https://github.com/dan-petty/devops-cli/issues/2278)) ([21654c6](https://github.com/dan-petty/devops-cli/commit/21654c619bfd0578bbd7e985237502d104b8fcd7))
* **roadmap:** intake leaves the sub-issues of a candidate's source out of the duplicate check ([#2275](https://github.com/dan-petty/devops-cli/issues/2275)) ([214028c](https://github.com/dan-petty/devops-cli/commit/214028cfb4e17f3a9f84170252ebebb995e9e564))
* **telemetry:** wait for abandoned dispatch workers before a test ends ([#2282](https://github.com/dan-petty/devops-cli/issues/2282)) ([51e8e61](https://github.com/dan-petty/devops-cli/commit/51e8e61c6dfe58f37e8d65588faf456c3a60a447))

## [0.6.0](https://github.com/dan-petty/devops-cli/compare/v0.5.0...v0.6.0) (2026-10-26)


### Features

* **k8s:** devops k8s doctor checks the gitea stack: tunnel host, anonymous refusal, clone url, registry token and no egress ([#2200](https://github.com/dan-petty/devops-cli/issues/2200)) ([4af6ea6](https://github.com/dan-petty/devops-cli/commit/4af6ea67c9bd4833eeb7c86b993c2747bd07c364)), closes [#2187](https://github.com/dan-petty/devops-cli/issues/2187)
* **telemetry:** centralized loki logql streamer, prometheus sparklines & trace waterfalls (tab-telemetry) ([#2213](https://github.com/dan-petty/devops-cli/issues/2213)) ([5d368c8](https://github.com/dan-petty/devops-cli/commit/5d368c8bf2b1efac5f54258a7cf456df2a90068c)), closes [#691](https://github.com/dan-petty/devops-cli/issues/691)
* **telemetry:** send devops-cli logs with trace ids to Loki ([#2224](https://github.com/dan-petty/devops-cli/issues/2224)) ([28c1607](https://github.com/dan-petty/devops-cli/commit/28c160790b09a902116ff62de1402d7329aa0acc)), closes [#813](https://github.com/dan-petty/devops-cli/issues/813)


### Bug Fixes

* **ai:** a transient rag lookup failure is not cached, so the same query recovers as soon as the backend answers ([#2222](https://github.com/dan-petty/devops-cli/issues/2222)) ([6f49beb](https://github.com/dan-petty/devops-cli/commit/6f49beb3bb33245b7234d3e27fab367214bf8fd2))
* **ai:** rag chunks stay under the embedder's real token limit, not a four-characters-per-token estimate ([#2221](https://github.com/dan-petty/devops-cli/issues/2221)) ([a21ad61](https://github.com/dan-petty/devops-cli/commit/a21ad61bf94c5a4191cfb1e19ef67ee5d9ffeeaa))
* **cli:** devops --dry-run on a command group given only its own options ([de49122](https://github.com/dan-petty/devops-cli/commit/de491222c60bd6c8b5c4f04d6a65dcfa2cf40e08))
* **cli:** devops --dry-run on a command group given only its own options previews it instead of crashing with IndexError ([#2259](https://github.com/dan-petty/devops-cli/issues/2259)) ([de49122](https://github.com/dan-petty/devops-cli/commit/de491222c60bd6c8b5c4f04d6a65dcfa2cf40e08))
* **cli:** drop devcontainer k8s auto-deploy for printed deploy-stack command ([#2227](https://github.com/dan-petty/devops-cli/issues/2227)) ([9278d3e](https://github.com/dan-petty/devops-cli/commit/9278d3eab20d59875c7107b8307a300db1bcde4b))
* **config:** service clients use only configured urls and never fall back to an unconfigured localhost default ([#2219](https://github.com/dan-petty/devops-cli/issues/2219)) ([5b3817d](https://github.com/dan-petty/devops-cli/commit/5b3817d4e237f78d75e5ad051d0afe4f89c522ae))
* **git:** git output the code parses is read NUL-separated, and git outcomes come from exit codes ([#2257](https://github.com/dan-petty/devops-cli/issues/2257)) ([db1d234](https://github.com/dan-petty/devops-cli/commit/db1d234954bba1e119cca1d4bfd632466b9ea8b8))
* **github:** devops pr check-readiness on a branch with no open pull request exits with a clean error ([#2270](https://github.com/dan-petty/devops-cli/issues/2270)) ([0a1b312](https://github.com/dan-petty/devops-cli/commit/0a1b312979334d8df86c066494749de06dc5b71e))
* **github:** project sync's board lookup and field provisioning fail closed on a failed read ([#2272](https://github.com/dan-petty/devops-cli/issues/2272)) ([40138f4](https://github.com/dan-petty/devops-cli/commit/40138f432b908cf030358ca59f92f2e192c17f2e))
* **k8s:** argo cd sync honours --prune and --force, rollout promote and abort reach the status subresource, and teardown's argo check fails closed ([#2246](https://github.com/dan-petty/devops-cli/issues/2246)) ([7f3743b](https://github.com/dan-petty/devops-cli/commit/7f3743bf161ca26b2b73db086747a64664f73643))
* **k8s:** authenticate service proxy with client auth settings and stream typed pod watch ([#2242](https://github.com/dan-petty/devops-cli/issues/2242)) ([1be8a79](https://github.com/dan-petty/devops-cli/commit/1be8a7926d8256dbd46af1087c8d8e94f686449f))
* **k8s:** dcgm-exporter's memory request and limit fit its measured footprint ([#2264](https://github.com/dan-petty/devops-cli/issues/2264)) ([4776f63](https://github.com/dan-petty/devops-cli/commit/4776f63206ffe667e11c35bf74b6073eaa00ea66))
* **k8s:** deploy-stack decides helm recovery from helm's json status and adopts existing resources with --take-ownership ([#2243](https://github.com/dan-petty/devops-cli/issues/2243)) ([c5dbafc](https://github.com/dan-petty/devops-cli/commit/c5dbafc4561d85b775c2962b3cf88896d8782a3e))
* **k8s:** send LogQL to Loki unchanged and restrict kubectl fallback ([#2228](https://github.com/dan-petty/devops-cli/issues/2228)) ([29743af](https://github.com/dan-petty/devops-cli/commit/29743af0da2f0a58b8a11cde778ab83f5ff2c614)), closes [#1431](https://github.com/dan-petty/devops-cli/issues/1431)
* **k8s:** the argo cd and grafana credential sync revokes and mints a token only when the service refused the old one, and reports every other failure ([#2210](https://github.com/dan-petty/devops-cli/issues/2210)) ([1bb164b](https://github.com/dan-petty/devops-cli/commit/1bb164bda6401d150741eaee4aa00ba62104da21))
* **mcp:** an mcp tool stops at its timeout, also when its command runs in-process ([#2269](https://github.com/dan-petty/devops-cli/issues/2269)) ([6cf8ff0](https://github.com/dan-petty/devops-cli/commit/6cf8ff0cdd1b01ea296febdfbb6bdfc4672cc9fb))
* **review:** a dependency advisory that admission rejects is not reported ([#2217](https://github.com/dan-petty/devops-cli/issues/2217)) ([4326906](https://github.com/dan-petty/devops-cli/commit/43269067f42638d8e2b284024db5cba6c14b9ede))
* **review:** a dependency advisory the base revision's pins already have is listed as pre-existing ([#2268](https://github.com/dan-petty/devops-cli/issues/2268)) ([00b3572](https://github.com/dan-petty/devops-cli/commit/00b3572ab6873580d0a09fec6f375fffb39bce13))
* **review:** a scanner finding that names a kubernetes object the reviewed commit lacks is rejected as object-not-in-commit ([#2225](https://github.com/dan-petty/devops-cli/issues/2225)) ([e69a4ff](https://github.com/dan-petty/devops-cli/commit/e69a4ff32c3405452cb368d40c27ae3f7a038265)), closes [#1352](https://github.com/dan-petty/devops-cli/issues/1352)
* **roadmap:** delete intake's refine hook; the cross-job rule is the one same-round refine trigger ([#2262](https://github.com/dan-petty/devops-cli/issues/2262)) ([90fc109](https://github.com/dan-petty/devops-cli/commit/90fc109ac53c367e56f78a19af18c01e892c5325))
* **roadmap:** intake files and places a candidate that the model judges a duplicate, and names the possible original, instead of dropping or closing it ([#2223](https://github.com/dan-petty/devops-cli/issues/2223)) ([050620d](https://github.com/dan-petty/devops-cli/commit/050620dfd4250884ec4177e19c97876a87aa7a09))
* **roadmap:** the roadmap service logs each failed job's own error with its repository, and a configuration error without a traceback ([#2229](https://github.com/dan-petty/devops-cli/issues/2229)) ([96238be](https://github.com/dan-petty/devops-cli/commit/96238be2d0ac27cd2431ba0861e21e16aaab6c23))
* **security:** the pluto, popeye and gitleaks adapters read what those tools actually write ([#2220](https://github.com/dan-petty/devops-cli/issues/2220)) ([6789a80](https://github.com/dan-petty/devops-cli/commit/6789a800d501d094708426e5c88c2185e5d60f21))
* **security:** vault leases requires --revoke and lease registry rebuilds on credential changes ([#2271](https://github.com/dan-petty/devops-cli/issues/2271)) ([efab944](https://github.com/dan-petty/devops-cli/commit/efab94453631c0f521dd6708af3e0c0273358360))
* **telemetry:** grafana aggregate lines sum and average the lines shown, read as dashed reference lines, and reach calls in flight ([#2215](https://github.com/dan-petty/devops-cli/issues/2215)) ([2084172](https://github.com/dan-petty/devops-cli/commit/2084172898662d8fef26e47f545ba7402f921fbd))
* **telemetry:** wait for background exporter threads on client shutdown ([#2274](https://github.com/dan-petty/devops-cli/issues/2274)) ([e6b86b2](https://github.com/dan-petty/devops-cli/commit/e6b86b27f6fb8b0b4dbd37878ac1c5968de2d431)), closes [#2273](https://github.com/dan-petty/devops-cli/issues/2273)

## [0.5.0](https://github.com/dan-petty/devops-cli/compare/v0.4.3...v0.5.0) (2026-10-25)


### Features

* **config:** devops config unset removes a key, and an unknown key's error names the line and that command ([#2207](https://github.com/dan-petty/devops-cli/issues/2207)) ([217e05b](https://github.com/dan-petty/devops-cli/commit/217e05bac917254e986431c129241d527d1fd51b)), closes [#2201](https://github.com/dan-petty/devops-cli/issues/2201)
* **k8s:** devops k8s volume move copies a local-path claim to a volume on another node and rebinds it, with argo cd paused and each step checked ([#2199](https://github.com/dan-petty/devops-cli/issues/2199)) ([8efee07](https://github.com/dan-petty/devops-cli/commit/8efee07dc755827601071be2547495b77ec2bd60)), closes [#2186](https://github.com/dan-petty/devops-cli/issues/2186)


### Bug Fixes

* **review:** exclude deleted files and record scanner failures per file ([#1140](https://github.com/dan-petty/devops-cli/issues/1140)) ([#2204](https://github.com/dan-petty/devops-cli/issues/2204)) ([cdc5070](https://github.com/dan-petty/devops-cli/commit/cdc5070d4d15be26245ddb4fcdd7f2581678b511))

## [0.4.3](https://github.com/dan-petty/devops-cli/compare/v0.4.2...v0.4.3) (2026-10-24)


### Bug Fixes

* **k8s:** a manual sync of the app-of-apps drops the homelab host overrides and every public hostname returns 404 ([#2195](https://github.com/dan-petty/devops-cli/issues/2195)) ([7c97467](https://github.com/dan-petty/devops-cli/commit/7c974672a09972b7ce47578fb489f0ce48166805))
* **review:** the review pipeline reports the eight failures it now swallows, and reads a file in one place ([#2196](https://github.com/dan-petty/devops-cli/issues/2196)) ([da401c6](https://github.com/dan-petty/devops-cli/commit/da401c6d82328eeaed03a8e0add7a405c3b28f1e)), closes [#2160](https://github.com/dan-petty/devops-cli/issues/2160)

## [0.4.2](https://github.com/dan-petty/devops-cli/compare/v0.4.1...v0.4.2) (2026-10-24)


### Bug Fixes

* **ai:** the default model, the bundle models, the benchmark default and the gpu matrix name models that the gateway serves ([#2188](https://github.com/dan-petty/devops-cli/issues/2188)) ([38f6afa](https://github.com/dan-petty/devops-cli/commit/38f6afa9e5da46526bcc81959658426a10f63b28))
* **cli:** devops docker prune removes stopped containers, unused networks and dangling images instead of failing on every engine ([#2190](https://github.com/dan-petty/devops-cli/issues/2190)) ([adc122b](https://github.com/dan-petty/devops-cli/commit/adc122bd3c03e9c4790ba2b3f04dc24052a8e037))
* **github:** gh calls no longer stall silently behind a fixed 60-call window ([#1118](https://github.com/dan-petty/devops-cli/issues/1118)) ([#2189](https://github.com/dan-petty/devops-cli/issues/2189)) ([ba239fa](https://github.com/dan-petty/devops-cli/commit/ba239fad6ced13d7e893886de50137b43d615017))

## [0.4.1](https://github.com/dan-petty/devops-cli/compare/v0.4.0...v0.4.1) (2026-10-24)


### Bug Fixes

* **ai:** sampling settings reach the model or are refused, review sessions record them, and the reply cache key includes them ([#2168](https://github.com/dan-petty/devops-cli/issues/2168)) ([e447c76](https://github.com/dan-petty/devops-cli/commit/e447c76daf48234ff56f5dc23a7b3e1c9f277d13)), closes [#1070](https://github.com/dan-petty/devops-cli/issues/1070)

## [0.4.0](https://github.com/dan-petty/devops-cli/compare/v0.3.1...v0.4.0) (2026-10-24)


### Features

* **ai:** AST support for YAML, Dockerfiles and Helm templates ([#2057](https://github.com/dan-petty/devops-cli/issues/2057)) ([d4d6816](https://github.com/dan-petty/devops-cli/commit/d4d6816c254f5d522bd5946c4dd8d9be5bfe3ae6)), closes [#539](https://github.com/dan-petty/devops-cli/issues/539)
* **ai:** devops ai gateway status reports failover while a route is failover:*, and failover --reset restores the default routes ([#2081](https://github.com/dan-petty/devops-cli/issues/2081)) ([0325fd6](https://github.com/dan-petty/devops-cli/commit/0325fd63bdc833d872390ffc446e2fcbdebfda8f))
* **ai:** llm gateway tuning cost from real traffic and no-load capacity estimates ([#2050](https://github.com/dan-petty/devops-cli/issues/2050)) ([1424eaa](https://github.com/dan-petty/devops-cli/commit/1424eaaad5612ba4230a24d6217d1342f0449563)), closes [#477](https://github.com/dan-petty/devops-cli/issues/477)
* **ai:** measured per-deployment capability probes in gateway tune ([#2083](https://github.com/dan-petty/devops-cli/issues/2083)) ([876df77](https://github.com/dan-petty/devops-cli/commit/876df77ae8f2efa674e0f8a02bc4a7d3fa9c75a1)), closes [#595](https://github.com/dan-petty/devops-cli/issues/595)
* **ai:** synthetic prompt adversaries for injection resistance ([#2032](https://github.com/dan-petty/devops-cli/issues/2032)) ([68f8830](https://github.com/dan-petty/devops-cli/commit/68f8830462c8f567e951ee7ce699bd08ed91b3e1)), closes [#417](https://github.com/dan-petty/devops-cli/issues/417)
* **ai:** the LLM stack dashboard shows latency per output token, and the Ollama docs record the keep-alive and slot-lease behaviour ([#2091](https://github.com/dan-petty/devops-cli/issues/2091)) ([1b25771](https://github.com/dan-petty/devops-cli/commit/1b2577140bf519ff535dde1f41998fc83fd2d245))
* **ci:** a pull request that changes the docs builds the pages site, so a site break fails before the merge ([#2021](https://github.com/dan-petty/devops-cli/issues/2021)) ([922989f](https://github.com/dan-petty/devops-cli/commit/922989fc429c7b88a8048f3f8520be3c72e416d7))
* **cli:** outward-facing capability and upstream maturity survey ([#2044](https://github.com/dan-petty/devops-cli/issues/2044)) ([e38fd02](https://github.com/dan-petty/devops-cli/commit/e38fd02626dd6b5fbc1ba8469454c3b91d79bfa1))
* **cli:** reasoning-token share in the spend ledger and provider-reported stream usage ([#2076](https://github.com/dan-petty/devops-cli/issues/2076)) ([f117292](https://github.com/dan-petty/devops-cli/commit/f117292392a5eeb8e5732d07d4d39f9e9a660204)), closes [#591](https://github.com/dan-petty/devops-cli/issues/591)
* **cli:** thinking-stream sanitizer initial state, unopened-tag count and thought cap ([#2074](https://github.com/dan-petty/devops-cli/issues/2074)) ([5eed986](https://github.com/dan-petty/devops-cli/commit/5eed986ab8da7dfaacc6aa3f57e9330acd56c4b8)), closes [#590](https://github.com/dan-petty/devops-cli/issues/590)
* **config:** a settings save writes only the changed keys and keeps the comments and unknown keys of config.yaml ([#2113](https://github.com/dan-petty/devops-cli/issues/2113)) ([c9767df](https://github.com/dan-petty/devops-cli/commit/c9767df15a3f7c59268f53b163974f9f7d50bb9d)), closes [#1999](https://github.com/dan-petty/devops-cli/issues/1999)
* **config:** devops config set stores a multi-line secret, such as a pem private key, from a file or stdin, never from argv or a one-line prompt ([#1962](https://github.com/dan-petty/devops-cli/issues/1962)) ([a1a3fac](https://github.com/dan-petty/devops-cli/commit/a1a3facd2cab37b140a59f27eb5df0184a4ce5d3))
* **k8s:** the homelab runs gitea under argo cd as a read-write internal forge, served in-cluster over http and to workstations at https://git.&lt;domain&gt; through the cloudflare tunnel, with its admin secret pushed from the keyring ([#2145](https://github.com/dan-petty/devops-cli/issues/2145)) ([7c4f143](https://github.com/dan-petty/devops-cli/commit/7c4f1439a78acec1d1bf66d1f73dccb493aa5f29)), closes [#1081](https://github.com/dan-petty/devops-cli/issues/1081)
* **review:** a review runs its tools in the network-less sandbox by default ([#2133](https://github.com/dan-petty/devops-cli/issues/2133)) ([b94adcc](https://github.com/dan-petty/devops-cli/commit/b94adcc1942dde23ab5b1567fcdadecb930d739b))
* **review:** golangci-lint sarif adapter for go in scan and review ([#2085](https://github.com/dan-petty/devops-cli/issues/2085)) ([bba1f5c](https://github.com/dan-petty/devops-cli/commit/bba1f5cea91bfb0fdfcaf29345660912f92642fd))
* **review:** group analysis is profiled as its own stage, and analysis.json counts dispatched, replayed and failed jobs apart ([#2049](https://github.com/dan-petty/devops-cli/issues/2049)) ([e2a5fee](https://github.com/dan-petty/devops-cli/commit/e2a5fee35fc7d79d34ffde3069623a3336179cec))
* **review:** the SARIF export of a review carries the ToolRun of each scan in the run of its tool ([#2103](https://github.com/dan-petty/devops-cli/issues/2103)) ([76a1b64](https://github.com/dan-petty/devops-cli/commit/76a1b646e0e6e0b2c3232323930936bf4df7d3ae))
* **roadmap:** refine looks at a blocked item again when the code its block cites changes on main ([#2082](https://github.com/dan-petty/devops-cli/issues/2082)) ([70578b6](https://github.com/dan-petty/devops-cli/commit/70578b69ba07153c7eed0884a1a3f83d6ee7ee99)), closes [#2005](https://github.com/dan-petty/devops-cli/issues/2005)
* **scan:** prompt-injection smuggling detector and canary audit ([#2067](https://github.com/dan-petty/devops-cli/issues/2067)) ([25c0d71](https://github.com/dan-petty/devops-cli/commit/25c0d7122287c86a469f24c887744a03ca0c3d82))
* **sdlc:** an OpenSpec change folder is the record of every item, and readiness checks its archive ([#2020](https://github.com/dan-petty/devops-cli/issues/2020)) ([2638317](https://github.com/dan-petty/devops-cli/commit/26383175e6e8b7c8e6771dfc1e693bd1880d48c1))


### Bug Fixes

* **ai:** a hosted gateway call is priced at the deployment model that the gateway names, not at the route name ([#2080](https://github.com/dan-petty/devops-cli/issues/2080)) ([9068795](https://github.com/dan-petty/devops-cli/commit/9068795086d58535a5cd3601f9d7ac5a1d5af7d4))
* **ai:** analyze --enhanced and ai agents use the metadata task model ([#1068](https://github.com/dan-petty/devops-cli/issues/1068)) ([#2155](https://github.com/dan-petty/devops-cli/issues/2155)) ([1897550](https://github.com/dan-petty/devops-cli/commit/1897550f386acb62a322dfe8237397b2c90b53f4))
* **ai:** embedding requests reach the spend ledger and the AI usage counters, priced against an embedding reference model ([#1970](https://github.com/dan-petty/devops-cli/issues/1970)) ([4bb052c](https://github.com/dan-petty/devops-cli/commit/4bb052c62ad0cf911edbed2cf1d1e640c3ba372d))
* **ai:** local savings use one reference price per request kind for every process, and an unknown model or reference warns instead of pricing at $0 ([#2062](https://github.com/dan-petty/devops-cli/issues/2062)) ([8a3b79e](https://github.com/dan-petty/devops-cli/commit/8a3b79e2c95b2096ff34e2620bdc9499cdfeb4af))
* **ai:** run ids with a trailing newline fail validation ([#2120](https://github.com/dan-petty/devops-cli/issues/2120)) ([3fe0bf6](https://github.com/dan-petty/devops-cli/commit/3fe0bf6c37275d3cdc1877f8c2bea47df1716847)), closes [#917](https://github.com/dan-petty/devops-cli/issues/917)
* **ai:** spend ledger records every attempt the gateway failed ([#1019](https://github.com/dan-petty/devops-cli/issues/1019)) ([#2140](https://github.com/dan-petty/devops-cli/issues/2140)) ([b170358](https://github.com/dan-petty/devops-cli/commit/b170358e2f76201c719d21531eea32b237762ee4))
* **ai:** the default fallback model and the open webui default model name models that the gateway serves ([#2126](https://github.com/dan-petty/devops-cli/issues/2126)) ([c030c1b](https://github.com/dan-petty/devops-cli/commit/c030c1b609e08b372e2d9d96bfd2d05fb9875dcd))
* **ai:** the gateway failover routes name models that a serving tier holds ([#2052](https://github.com/dan-petty/devops-cli/issues/2052)) ([84b5cb3](https://github.com/dan-petty/devops-cli/commit/84b5cb3eceb6b99913e07b5b7f4373f55332cb28))
* **ai:** the spend series exists at $0, a gateway call counts as local or hosted by the backend that served it, and the ledger exposition stops reusing the OTLP names ([#2040](https://github.com/dan-petty/devops-cli/issues/2040)) ([02540c0](https://github.com/dan-petty/devops-cli/commit/02540c00b40066627d9dbc91fb1df2a7b53075d8))
* **argocd:** every application pins automated sync enabled in git, so the devops application syncs again and a ui pause is reverted ([#2017](https://github.com/dan-petty/devops-cli/issues/2017)) ([6030445](https://github.com/dan-petty/devops-cli/commit/6030445c7b38feba3cded643848ade9038f9f864))
* **argo:** derive workflow pod names and default container to main ([#2123](https://github.com/dan-petty/devops-cli/issues/2123)) ([a5aaccc](https://github.com/dan-petty/devops-cli/commit/a5aaccc9f16e43fa3ebc04d4a8ea2492c8d1026a)), closes [#988](https://github.com/dan-petty/devops-cli/issues/988)
* **cache:** one circuit breaker with open, cooldown and half-open states guards the valkey cache tier and the rag lookup pause ([#2109](https://github.com/dan-petty/devops-cli/issues/2109)) ([9d61b39](https://github.com/dan-petty/devops-cli/commit/9d61b39d142c0b5a9b2116e0ee49629e8ccf9ad6))
* **ci:** a commit runs no test suite in pre-commit; the pre-push gate and CI run the tests ([#2090](https://github.com/dan-petty/devops-cli/issues/2090)) ([08551af](https://github.com/dan-petty/devops-cli/commit/08551af0671f50a8468fb8a748573b9c990626b7))
* **config:** devops config init names the file it writes, not the default config path ([#2065](https://github.com/dan-petty/devops-cli/issues/2065)) ([9772769](https://github.com/dan-petty/devops-cli/commit/9772769a03dcd04d126aed87dc683c069fc8db40))
* **config:** validate settings field types on load and assignment ([#2124](https://github.com/dan-petty/devops-cli/issues/2124)) ([6e1bf4a](https://github.com/dan-petty/devops-cli/commit/6e1bf4ad9f74b1277bc9704109c081d60525decf))
* **deps:** fastmcp 4.1.2 and filelock 4.2.4 fix seven advisories, which fail the audit check of every pull request ([#2013](https://github.com/dan-petty/devops-cli/issues/2013)) ([188c107](https://github.com/dan-petty/devops-cli/commit/188c10707378e21316651b29bc20d8d952f98349))
* **deps:** virtualenv 21.14.13 fixes GHSA-cx6f-vjhg-g3cc, which fails the audit check of every pull request ([#2006](https://github.com/dan-petty/devops-cli/issues/2006)) ([05211d5](https://github.com/dan-petty/devops-cli/commit/05211d5c3446ca9753fbf440668593c12704a320))
* **docs:** the Pages build applies the site settings, which live in docs/_config.yml only ([#2068](https://github.com/dan-petty/devops-cli/issues/2068)) ([6c3f27b](https://github.com/dan-petty/devops-cli/commit/6c3f27bb5ccce805066e6b2a2f07c7855ff0ecee)), closes [#2001](https://github.com/dan-petty/devops-cli/issues/2001)
* **github:** devops gh api rate_limit --jq fails with Invalid rate_limit payload format ([#1963](https://github.com/dan-petty/devops-cli/issues/1963)) ([79626a8](https://github.com/dan-petty/devops-cli/commit/79626a803287b3f6a9d85a3d1f58fe66fa251086))
* **k8s:** a changed gateway ConfigMap rolls the gateway deployment, so deploy-stack never leaves a stale pod ([#2033](https://github.com/dan-petty/devops-cli/issues/2033)) ([70e775f](https://github.com/dan-petty/devops-cli/commit/70e775f6e17b19905caf846748d0d538b03a62e6))
* **k8s:** grafana moves to the grafana-community chart on a grafana 13 release that fixes cve-2026-76154, and provisioning prunes removed datasources ([#2023](https://github.com/dan-petty/devops-cli/issues/2023)) ([6d978ff](https://github.com/dan-petty/devops-cli/commit/6d978fffc69a5e220917be4a2e010b6eb837630a))
* **k8s:** open webui, the ollama ingress, the gateway and the cli's default ollama service point at tiers that have pods ([#1965](https://github.com/dan-petty/devops-cli/issues/1965)) ([0bff85f](https://github.com/dan-petty/devops-cli/commit/0bff85f1c77ef0d8faeccf6316e10c09aa6b3366))
* **k8s:** qdrant requires its api key, and open webui sends it ([#2014](https://github.com/dan-petty/devops-cli/issues/2014)) ([8810767](https://github.com/dan-petty/devops-cli/commit/88107676188d47b0d769ba9ebd85292e1352d5bc))
* **k8s:** start minikube with calico cni and align bootstrap help ([#2122](https://github.com/dan-petty/devops-cli/issues/2122)) ([e7b9db7](https://github.com/dan-petty/devops-cli/commit/e7b9db797ceb7af16402986fa7990793c8c6227d)), closes [#990](https://github.com/dan-petty/devops-cli/issues/990)
* **k8s:** stateful local-path volumes bind on nodes with disk headroom instead of the control-plane node's 84%-full root disk ([#2150](https://github.com/dan-petty/devops-cli/issues/2150)) ([3a00772](https://github.com/dan-petty/devops-cli/commit/3a0077260627b0acdae66d93d43ab14ffae76686))
* **k8s:** the gateway sends embeddings to every serving ollama tier, fastest first, so a rag batch never waits behind the slow tier ([#1991](https://github.com/dan-petty/devops-cli/issues/1991)) ([060ccd6](https://github.com/dan-petty/devops-cli/commit/060ccd6414e0aaddaee6356b8b2a3482ff3accbf))
* **k8s:** the llm valkey cache requires a password and admits only its clients, like valkey-runs ([#1981](https://github.com/dan-petty/devops-cli/issues/1981)) ([a752a14](https://github.com/dan-petty/devops-cli/commit/a752a14ae940f6a394fb077e1f6f1915a37951af))
* **k8s:** the shared llm valkey has a memory bound below its container limit and refuses writes at the bound ([#2097](https://github.com/dan-petty/devops-cli/issues/2097)) ([760b197](https://github.com/dan-petty/devops-cli/commit/760b197d17d1c6f2e242585e4a72e7709078b485)), closes [#711](https://github.com/dan-petty/devops-cli/issues/711)
* **k8s:** the unauthenticated in-cluster image registry leaves the cluster, and gitea's container registry replaces it ([#2136](https://github.com/dan-petty/devops-cli/issues/2136)) ([df8e2ee](https://github.com/dan-petty/devops-cli/commit/df8e2ee5e99a45efe2430a92717ee60eff67d9e3))
* **monitoring:** grafana pins its four drilldown app plugins at the 3.x releases that grafana 13 needs ([#2056](https://github.com/dan-petty/devops-cli/issues/2056)) ([1c60233](https://github.com/dan-petty/devops-cli/commit/1c602332d568c5c4b3ad3d130f3786f8e832b3d4))
* **monitoring:** grafana provisioning deletes the read-only jaeger datasource that the grafana 12 install left behind ([#2037](https://github.com/dan-petty/devops-cli/issues/2037)) ([787d760](https://github.com/dan-petty/devops-cli/commit/787d760360efda61ed37d755c6ed38cc138e0067))
* **monitoring:** the alloy-metrics write-ahead log survives a pod restart ([#2137](https://github.com/dan-petty/devops-cli/issues/2137)) ([77a6430](https://github.com/dan-petty/devops-cli/commit/77a6430ad8ae8c9c7b25b3d0a39e0ff82dddd693)), closes [#1967](https://github.com/dan-petty/devops-cli/issues/1967)
* **monitoring:** the Grafana rate panels hold two samples, the dashboard queries match the live series, and the k8s-monitoring values use the chart's documented settings ([#1958](https://github.com/dan-petty/devops-cli/issues/1958)) ([4b06d31](https://github.com/dan-petty/devops-cli/commit/4b06d316f6a6067f174b735ffa9c936e0e581124))
* **rag:** a slow embedding batch halves the batch size once for the size it was sent at, and the size grows back only after a cooldown and below a margin ([#2088](https://github.com/dan-petty/devops-cli/issues/2088)) ([21a49cd](https://github.com/dan-petty/devops-cli/commit/21a49cdd874c640838f7e53f6a2986b9826281a0))
* **rag:** a timed-out embedding batch closes the HTTP client that the other parallel batches use, so intake reports a healthy gateway as down ([#2030](https://github.com/dan-petty/devops-cli/issues/2030)) ([e4e0694](https://github.com/dan-petty/devops-cli/commit/e4e069490e81fabe56a340bee096a656353aecf4))
* **review:** --pre-analysis-only stops after pre-analysis and runs no evidence tool ([#2066](https://github.com/dan-petty/devops-cli/issues/2066)) ([4b9fa24](https://github.com/dan-petty/devops-cli/commit/4b9fa242e36f63f7c8bb34787f129981436532be))
* **review:** a one-file path review takes minutes in the payloads stage because the lockfile coverage scan walks the whole checkout and mypy starts with an empty cache ([#2048](https://github.com/dan-petty/devops-cli/issues/2048)) ([ae4acaf](https://github.com/dan-petty/devops-cli/commit/ae4acafc884d8e8f210748471db84aa177d163b0))
* **review:** a review records its prompt digest when it starts, and a benchmark arm refuses runs whose prompts or code changed ([#2134](https://github.com/dan-petty/devops-cli/issues/2134)) ([51d0f16](https://github.com/dan-petty/devops-cli/commit/51d0f16f30b73e1b7a02f3ce11dbbd6afac0f916)), closes [#1050](https://github.com/dan-petty/devops-cli/issues/1050)
* **review:** classify C++ files and Helm chart templates in file analysis ([#2055](https://github.com/dan-petty/devops-cli/issues/2055)) ([3807f8f](https://github.com/dan-petty/devops-cli/commit/3807f8f66c57ce9efac18085628fe70787b0bd5f))
* **review:** review path --watch reviews only the files that changed ([#2135](https://github.com/dan-petty/devops-cli/issues/2135)) ([f4d7066](https://github.com/dan-petty/devops-cli/commit/f4d7066b12ea727609dfaeabc8ef77c6db47f03f))
* **review:** the binary digest of a Python review tool names its package, not its launcher script ([#2099](https://github.com/dan-petty/devops-cli/issues/2099)) ([51a8e0a](https://github.com/dan-petty/devops-cli/commit/51a8e0a58fd81c5520e7c6129a8ae8f19f1208ae))
* **roadmap:** a backlog full of ready items does not stop refine before it looks at the backlog's other new items ([#2071](https://github.com/dan-petty/devops-cli/issues/2071)) ([0a2bfe1](https://github.com/dan-petty/devops-cli/commit/0a2bfe1f0b4c9da5a055e201d13a348f5b398f93))
* **roadmap:** intake calls a candidate a duplicate only when it asks for the same change, not when it shares a theme ([#2018](https://github.com/dan-petty/devops-cli/issues/2018)) ([64e74dd](https://github.com/dan-petty/devops-cli/commit/64e74dd2fd88bd344b0afc2aaf685b2f0ec75096))
* **roadmap:** intake judges a split part a duplicate of the issue that its --source names, so the part gets no issue ([#2038](https://github.com/dan-petty/devops-cli/issues/2038)) ([0f254f0](https://github.com/dan-petty/devops-cli/commit/0f254f000c4a85f772fdea892b195fda92ccf86c))
* **roadmap:** refine gives every item it cannot ready a next step instead of skipping it as unchanged ([#2016](https://github.com/dan-petty/devops-cli/issues/2016)) ([354d281](https://github.com/dan-petty/devops-cli/commit/354d2816cea815c15773be7f469381f624146520))
* **security:** a gitleaks list scan keeps its start and end times in sarif ([#2119](https://github.com/dan-petty/devops-cli/issues/2119)) ([8ff16de](https://github.com/dan-petty/devops-cli/commit/8ff16de61fd1e68c4f332df876a10d2cd0767afa))
* **security:** secret masking tells code from literals by the file's syntax, not by receiver names ([#2104](https://github.com/dan-petty/devops-cli/issues/2104)) ([a18a342](https://github.com/dan-petty/devops-cli/commit/a18a3424e3ca495ae36d1a136b8892d6aafae12d)), closes [#889](https://github.com/dan-petty/devops-cli/issues/889)
* **security:** the agent scan tools run the scanner adapters and report a missing or failed scan as such, not as clean ([#2112](https://github.com/dan-petty/devops-cli/issues/2112)) ([02fee43](https://github.com/dan-petty/devops-cli/commit/02fee43a7dcb3af0aa94750c6fc75bc878ada3da))
* **service:** roadmap-service exports its AI usage counters after every lane batch, under one series identity that survives a pod restart ([#2042](https://github.com/dan-petty/devops-cli/issues/2042)) ([a97a93d](https://github.com/dan-petty/devops-cli/commit/a97a93db74c91650ba0df240f8f2fabdb60b5faa))
* **telemetry:** a command span sets no process.command_line, which the conventions give to the full command line ([#2075](https://github.com/dan-petty/devops-cli/issues/2075)) ([a9835d1](https://github.com/dan-petty/devops-cli/commit/a9835d15b0668e0e6b62cf2fe54c4c396d3177e0))
* **telemetry:** a subprocess span holds the executable and the argument count, and the arguments only when a person turns them on ([#2061](https://github.com/dan-petty/devops-cli/issues/2061)) ([0983f6c](https://github.com/dan-petty/devops-cli/commit/0983f6c73c8e349b2c88d4ace16fa1ed67ff246f))
* **telemetry:** a usage error records its error class, never the argument text, and counts as a failed command ([#2063](https://github.com/dan-petty/devops-cli/issues/2063)) ([53c9106](https://github.com/dan-petty/devops-cli/commit/53c9106a1c9b6443eb56fed8f525a5f9ffbe9606))
* **telemetry:** the profile span holds the command path and the argument count, never the argument values ([#2077](https://github.com/dan-petty/devops-cli/issues/2077)) ([0a2d42e](https://github.com/dan-petty/devops-cli/commit/0a2d42e223d5fdd42c8c9d75862e31a9a9a845be))
* **tests:** a test that writes a real config.yaml fails at the write and names itself, and every config write keeps a backup and a change record ([#2019](https://github.com/dan-petty/devops-cli/issues/2019)) ([ce0c21f](https://github.com/dan-petty/devops-cli/commit/ce0c21f1664f478069b8d89a8496e5c78b6f1fd3))
* **tests:** four tests that wait for a time window fail under host load ([#2139](https://github.com/dan-petty/devops-cli/issues/2139)) ([fc12d05](https://github.com/dan-petty/devops-cli/commit/fc12d05787e07f6cce820aea71cea0bcea2e9dc8))
* **tests:** the synthetic tiktoken encoding of the prepared-cache test stays in tiktoken's registry, so later token counts on that worker are per byte ([#2015](https://github.com/dan-petty/devops-cli/issues/2015)) ([bd5f648](https://github.com/dan-petty/devops-cli/commit/bd5f6484d30c7985bc03fd3765a19f99bece20f9))
* **tests:** twelve tests still assert elapsed wall-clock time, and no check enforces the rule in docs/TESTING.md ([#1973](https://github.com/dan-petty/devops-cli/issues/1973)) ([dd6052c](https://github.com/dan-petty/devops-cli/commit/dd6052c0f0e950c93c2ddc5fa0c5d28ef1aab770))
* **valkey:** valkey.url is one validated url, its path names the database, and the separate host, port and db settings go ([#2087](https://github.com/dan-petty/devops-cli/issues/2087)) ([12fa20c](https://github.com/dan-petty/devops-cli/commit/12fa20c2e95dff1700c3c093d9df3627dd480a14)), closes [#2060](https://github.com/dan-petty/devops-cli/issues/2060)
* **valkey:** valkey.url keeps its scheme, so a valkeys url dials tls with host name checks ([#2064](https://github.com/dan-petty/devops-cli/issues/2064)) ([5f36c4c](https://github.com/dan-petty/devops-cli/commit/5f36c4cd05fb0547d25ca5aefb56692576c664b6))


### Performance Improvements

* **review:** pre-analysis of a 17-file pull request takes four minutes because it refreshes metadata for 2,339 files ([#1980](https://github.com/dan-petty/devops-cli/issues/1980)) ([45f1669](https://github.com/dan-petty/devops-cli/commit/45f166911b6beba7c035fd941b56a4052b6390a1))


### Code Refactoring

* **cli:** one process runner owns execution, process groups and dry-run ([#2117](https://github.com/dan-petty/devops-cli/issues/2117)) ([0a9725d](https://github.com/dan-petty/devops-cli/commit/0a9725d48b52cbbc78de2685bc5f9db3edd45f81))
* **config:** remove config barrel and unused config names, and stop package init re-exports ([#2102](https://github.com/dan-petty/devops-cli/issues/2102)) ([ae3c0c6](https://github.com/dan-petty/devops-cli/commit/ae3c0c605c29774dfd4f71483f02b8fb0e243b09)), closes [#776](https://github.com/dan-petty/devops-cli/issues/776)
* **github:** the board's priority field is the only priority source, and stray type labels merge into type/bug ([#2105](https://github.com/dan-petty/devops-cli/issues/2105)) ([f730cdb](https://github.com/dan-petty/devops-cli/commit/f730cdbc57ead1b150a44f9cf54a23687ed4db98)), closes [#880](https://github.com/dan-petty/devops-cli/issues/880)
* **review:** the review orchestrator and the scanners take the reviewed workspace from their caller, and no review or scanner module reads Path.cwd() ([#2128](https://github.com/dan-petty/devops-cli/issues/2128)) ([11ddf0f](https://github.com/dan-petty/devops-cli/commit/11ddf0f0e49a546b5ffb338d5e58a426df1890cf))
* **review:** the synthetic corpus drops contradict-documented-default, which no tool can detect ([#2053](https://github.com/dan-petty/devops-cli/issues/2053)) ([3c8f627](https://github.com/dan-petty/devops-cli/commit/3c8f62759cd03bddd57a42a8c29b82fd74781ceb))
* **roadmap:** intake files every new candidate, with no agent filing quota ([#1964](https://github.com/dan-petty/devops-cli/issues/1964)) ([4ed262a](https://github.com/dan-petty/devops-cli/commit/4ed262a7a5493e429b7e856dbacf30517e8f5579))
* **sdlc:** the task files that merged after the openspec switch are deleted, and the decommission check is strict ([#2051](https://github.com/dan-petty/devops-cli/issues/2051)) ([5787ea7](https://github.com/dan-petty/devops-cli/commit/5787ea72250df811126ec21d3d0c8254453615f0))
* **security:** mypy and the review canary start their tools through a ToolExecutor ([#2114](https://github.com/dan-petty/devops-cli/issues/2114)) ([34bae84](https://github.com/dan-petty/devops-cli/commit/34bae841b38d001d1b626852653b3d479c9cc274))

## [0.3.1](https://github.com/dan-petty/devops-cli/compare/v0.3.0...v0.3.1) (2026-10-23)


### Performance Improvements

* **ci:** the release builds the service image for linux/amd64 only, with no QEMU ([#1956](https://github.com/dan-petty/devops-cli/issues/1956)) ([6be0c3d](https://github.com/dan-petty/devops-cli/commit/6be0c3d8ae7d0a1278582b0f6a5278e38beb4af7))

## [0.3.0](https://github.com/dan-petty/devops-cli/compare/v0.2.39...v0.3.0) (2026-10-23)


### Features

* **release:** release-please makes every release from main ([#1952](https://github.com/dan-petty/devops-cli/issues/1952)) ([64dd981](https://github.com/dan-petty/devops-cli/commit/64dd981875db5e976ef6fdd07d2a9efdbe610d6d))

## [0.2.39] - 2026-10-23

### Added
- The roadmap Service's webhook router has one route per declared provider (`POST /webhooks/github` today), verifies each provider its own way (GitHub's HMAC-SHA256 signature), validates the signed body into a typed pydantic model, and delivers each event only to the consumers subscribed to it. The roadmap consumer takes `issues`, `pull_request`, `milestone` and `release`. Every other event, a `push`, `issue_comment` or `create` included, is acknowledged with `no_subscriber` and starts no round. Each delivery writes one log record with its provider, event, action, delivery, repository and outcome, and `devops_cli_service_webhook_deliveries_total` counts it by provider, event and outcome ([ADR 0009](docs/adr/0009-one-webhook-router-delivers-each-event-to-the-consumers-subscribed-to-it.md), [#1386](https://github.com/dan-petty/devops-cli/issues/1386)).
- The Argo Workflows controller runs in its own namespace, `argo-workflows`, under Pod Security `restricted` and a default-deny perimeter, installed by Argo CD and by `devops k8s deploy-stack --stack infra`. A `--version` WorkflowTemplate with no GitHub request and no Secret measures a Workflow's start-up time and the API server's load, for the go/no-go on moving the roadmap Service's jobs onto it ([ADR 0008](docs/adr/0008-argo-workflows-run-the-roadmap-jobs-after-a-measured-go.md)). The argo CLI pin moves to v4.1.5, the chart's app version ([#1535](https://github.com/dan-petty/devops-cli/issues/1535)).
- ADR 0012 decides the release model. Under it, release-please will replace the `release/vX.Y.Z` branch, the hand-made cut and the bespoke cut, collector and compactor code ([ADR 0012](docs/adr/0012-releases-are-derived-by-release-please-from-trunk-and-milestones-are-planning-buckets.md), [#1751](https://github.com/dan-petty/devops-cli/issues/1751)).
  - Topic pull requests will target `main`. release-please will derive each version from the Conventional Commit titles, open the release pull request and write the changelog.
  - Merging that pull request will publish the release and create the tag as the last write. Argo CD will follow the semver tags. A milestone will be a planning bucket, not a version.
  - ADR 0012 supersedes ADR 0011, which kept a prepare workflow and `towncrier` fragments.
  - It measures v0.2.36 and v0.2.37 (75 and 107 minutes, release pull requests of 188 and 990 files). It compares six options, decides 18 points that needed the owner and orders 14 steps.
- ADR 0010 records the adoption of OpenSpec as the spec and change-proposal layer, so that planning is consistent across Claude Code, Gemini CLI and Copilot, with the roadmap jobs joining in the last two steps: every item becomes a change folder `openspec/changes/<issue>-<slug>/` that replaces its task file, the pull request that closes a change archives it into `openspec/specs/`, OpenSpec 1.14.3 is pinned in `tools.lock` and run with telemetry off, and the ADR names every rule, check and test that changes, the ordered items that carry the migration and the conditions under which to revisit ([#1753](https://github.com/dan-petty/devops-cli/issues/1753)).
- `devops install-tools` installs a third kind of tool, a Node tool, with `npm ci --ignore-scripts` from a committed `package-lock.json` that npm checks against the sha512 of every package, and OpenSpec 1.14.3 is the first. The install is staged and renamed into place, so a package that fails its checksum leaves no partial install, and it fails first, naming `npm`, when `npm` is missing; `devops devcontainer post-create` warns instead. The devcontainer, its template, the CI workflow and the committed Claude Code settings opt out of OpenSpec's telemetry and update check, the `node` feature is pinned to Node 24 with a `.node-version` file, and the `audit` check of `devops ci` also runs `npm audit` on the lockfile, so a vulnerable pin fails the gate, and `devops ci audit`, `devops ci maintain` and the gate's row read npm's JSON report to tell a finding from an audit that could not run, since npm exits 1 for both ([#1842](https://github.com/dan-petty/devops-cli/issues/1842)).
- OpenSpec has a scaffold, a gate and an archive command. `openspec/config.yaml` holds the planning conventions, and the generated skills of four workflows are committed under `.claude/skills/` and `.agents/skills/`. `devops openspec check` is a row of `devops ci`. It validates every change and every archived change. It compares the committed skills with a regeneration. It renders the instructions of a probe change. It finds a requirement that two changes rewrite. `devops openspec regenerate` rewrites the skills. `devops openspec archive <change>` archives a change and then runs `openspec validate --all --strict`. It exits 1 when either run fails, and it prints the whole output of the run that failed. The three commands run the pinned OpenSpec with telemetry off, under an isolated configuration ([#1844](https://github.com/dan-petty/devops-cli/issues/1844)).
- `devops ai agents` writes a `GEMINI.md` pointer stub, and this repository commits one. Gemini CLI loads `GEMINI.md` by default. It reads `AGENTS.md` only through its `context.fileName` setting. The stub holds an `@./AGENTS.md` import line, the form that the Gemini CLI documentation (v0.65.0) shows. One table, `POINTER_STUBS`, now chooses the title, the tool name, the link and the import line of each stub ([#1845](https://github.com/dan-petty/devops-cli/issues/1845)).
- Agents and `devops ai` write in ASD-STE100 Simplified Technical English. `AGENTS.md` has one rule that asks for it. The system prompt of each free-text model call ends with a short request for it, from `src/devops_cli/ai/tasks/style_ste100.md`. The request tells the model to keep quotations, search queries, keyword lists and output formats as they are. Nothing checks the style. No existing string changes ([#1866](https://github.com/dan-petty/devops-cli/issues/1866)).
- `devops install-tools` installs gh-dash 4.26.2, a terminal dashboard for GitHub pull requests and issues. `tools.lock` holds a SHA-256 for each of its four platforms. The file `.gh-dash.yml` sets four pull request tabs, three issue tabs, one notification tab and a refresh every 60 minutes. Each pull request tab lists the oldest pull request first. The keys `w`, `T`, `D` and `d` run `devops pr monitor`, `checks`, `threads list` and `diff`. `tests/test_gh_dash_config.py` checks the file against the published gh-dash schema ([#1882](https://github.com/dan-petty/devops-cli/issues/1882)).
- `devops install-tools` installs tuicr 0.27.0, a terminal program where a person reviews the diff of an agent and adds typed comments. `tools.lock` holds a SHA-256 for each of its four platforms. The template `.devops/tuicr.config.toml` turns off the update check and defines the comment types `issue`, `question` and `nit`. The file `.tuicrignore` hides the generated documents from the person. The "Human Review Round" bullet in `docs/SDLC.md` Phase 6 tells the agent to read the comments as JSON and to reply by comment id. The agent never runs the tuicr commands that delete a session or call `gh` ([#1884](https://github.com/dan-petty/devops-cli/issues/1884)).

### Changed
- The LLM gateway serves `qwen3-embedding:0.6b` as its embedding model in place of `bge-m3:latest`. A person measured both on this repository on 2026-10-22. `qwen3-embedding:0.6b` ranked the right code chunk first for 74 of 100 queries, and `bge-m3:latest` did so for 53. The group runs on the same slow-tier deployment. The READMEs, the default gateway routes, the GPU matrix and the example configuration of the in-cluster jobs name the new model ([#481](https://github.com/dan-petty/devops-cli/issues/481)).
- To deploy the change, run `devops k8s deploy-stack --stack llm`, then run `kubectl -n llm rollout restart deployment/llm-gateway`, because the gateway reads its configuration at start. Then run `devops k8s deploy-stack --stack devops`. A `devops-cli-config` deployed earlier names `bge-m3:latest` until you do, and the gateway no longer serves that model ([#481](https://github.com/dan-petty/devops-cli/issues/481)).
- To use the new model, set `ai.tasks.embedding` in your own `config.yaml`. Run `export DEVOPS_CLI_AI_TASK_EMBEDDING_TIMEOUT=120`, then `devops ai rag clear --force`, `devops ai rag index --force` and `devops ai rag index-kb`. The index refuses a collection that another model indexed ([#481](https://github.com/dan-petty/devops-cli/issues/481)).
- `GitHubClient` is a typed client over the GitHub session. It reads pull requests, their files, a file at a commit, a merge base and the repositories of an organization. It returns the models `PullRequest`, `CommitRef` and `PullRequestFile`. The session applies its quota ledger, retry rules and error classes to each call. `devops review pr`, `devops ai analyze pr` and `devops repos clone-org` use it ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- A GitHub read that fails now ends the command with the GitHub error. Before, every failure looked like a missing file. `get_merge_base` returns nothing for a 404 only. `get_file_at` returns nothing for a 404. It also returns nothing for a directory, a link, a submodule, a file over 1 MB or bytes that are not UTF-8 ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- `devops review pr --post` now stops when it cannot read the files of the pull request. Before, it posted a comment that named no file ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- `devops repos clone-org <login>` for the signed-in account lists the repositories that the account owns. PyGithub also listed the repositories of collaborators and organizations ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- `devops ssh register` and `devops ssh rotate` register the authentication key and the signing key through the session. A 422 counts as registered when the key listing holds the key or cannot be read. The error for a token without the scope gives the `gh auth refresh` command that adds it. `SSHRegistrationError` is now a `GitHubOperationError` ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- `devops gh labels sync` and `devops gh labels list` use the `gh` client only ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- `devops roadmap refine` judges each item by the body its issue listing already carried, so an item nothing changed costs no body read and no model call until its text changes, where each one cost a request to GitHub in every round ([#1539](https://github.com/dan-petty/devops-cli/issues/1539)).
- AGENTS.md asks for a written cost (tokens to implement, maintain and fix, and elapsed time) before internal code is built where an open tool covers the capability, and the feature request form requires naming the existing tool considered ([#1833](https://github.com/dan-petty/devops-cli/issues/1833)).
- The `devops ai agents` command read its own second copy of the file table. The change deletes that copy. The command now reads `DEFAULT_AGENT_FILES` ([#1845](https://github.com/dan-petty/devops-cli/issues/1845)).
- The style request changes the system prompt of each free-text model call. Every cached reply is cold after the upgrade. Older benchmark reports and review prompt digests do not compare with new ones ([#1866](https://github.com/dan-petty/devops-cli/issues/1866)).
- `devops ci` and the pre-commit `ruff-check` hook now run `ruff check --config pyproject.toml`. No nested Ruff file can lift the complexity cap of 10. Three tests now check the resolved Ruff settings, the files that Ruff walks and every `ruff check` command. They replace the key allowlists and the table of 38 escape cases ([#1870](https://github.com/dan-petty/devops-cli/issues/1870)).
- A `scripts/` directory may now exist. `test_no_stray_scripts_in_project_root` no longer fails when it does. A `.py` or `.sh` file in the project root still fails. The `AGENTS.md` rule "Scratch Work Stays Untracked" lets a committed helper script live in `scripts/` as a PEP 723 file. The rule no longer names the scratch path of one vendor's agent ([#1872](https://github.com/dan-petty/devops-cli/issues/1872)).
- `AGENTS.md` says that a convention is never a reason to keep or write custom code. Replacing a check with a standard tool is not lowering a threshold when the tool enforces at least the same property ([#1874](https://github.com/dan-petty/devops-cli/issues/1874)).
- The bullet "Never Lower Security Standards or Quality Thresholds" in `AGENTS.md` now holds the compliance bullet. The merge keeps one sentence of it: "Every change meets the project standards." ([#1874](https://github.com/dan-petty/devops-cli/issues/1874)).
- `AGENTS.md` drops the `Gated` terminology rule, the headroom targets, the duplicate intake and naming bullets and the empty-queue sentence. The file is 1,104 characters shorter ([#1874](https://github.com/dan-petty/devops-cli/issues/1874)).
- An agent files its own new candidate with `devops roadmap intake --confirm`. An agent asks a person to run `devops roadmap return --confirm` ([#1874](https://github.com/dan-petty/devops-cli/issues/1874)).
- The secrets rule in `AGENTS.md` gives the OS keyring, HashiCorp Vault, a Kubernetes Secret and the credential store of the owning tool as examples of a secret store. The list is open ([#1874](https://github.com/dan-petty/devops-cli/issues/1874)).
- `devops ai agents` writes the new never-lower, root-cause and `roadmap return` wording into other repositories. It no longer writes the compliance bullet or the empty-queue sentence ([#1874](https://github.com/dan-petty/devops-cli/issues/1874)).
- The six review-only guards of `AGENTS.md` section 5 now live in `.devops/review.md`, which `nearest_review_conventions` reads. `AGENTS.md` keeps one pointer bullet and is 1,611 characters shorter. GitHub Copilot code review reads `AGENTS.md` and not `.devops/review.md`, so it no longer sees the guards ([#1881](https://github.com/dan-petty/devops-cli/issues/1881)).

### Removed
- The project no longer uses PyGithub. This change removes the dependency, its knowledge-base manual and every import. `GitHubClient` and SSH key registration now send each GitHub REST call through the GitHub session ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- This change removes the `gh` path of SSH key registration and the label methods of `GitHubClient`. It also removes `GhCliClient.edit_issue` and `SSHKeyInfo`. The project is pre-1.0 and keeps no shim ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- This change removes these `GitHubClient` methods, which no code called: `get_user_ssh_keys`, `add_user_ssh_key`, `delete_user_ssh_key`, `create_pr_review_comment`, `get_issues`, `create_issue`, `edit_issue`, `get_pages_info` and `get_pages_builds`. The module function `get_pages_builds` in `github/pages.py` stays ([#891](https://github.com/dan-petty/devops-cli/issues/891)).
- The durable-execution engine and the agent capabilities that no command used are deleted: `devops_cli.ai.durable` (the Temporal, DBOS and Prefect engine bridges with `is_temporal_available`, `is_dbos_available`, `is_prefect_available` and `get_available_durable_engines`, the local SQLite step store and `resolve_durability_capability`), and the media, step-persistence, managed-prompt, spend-guard and synthesis-protocol modules of `devops_cli.ai.agents`. The `ai.durable` settings (`engine`, `store_path`, `task_queue`, `workflow_id_prefix`) were never read and are removed; a `config.yaml` that still has the block loads unchanged, and the block is ignored. `BudgetExceededError`, `sanitize_prompt_injection` and `format_prompt_data` go with their only callers ([#1121](https://github.com/dan-petty/devops-cli/issues/1121)).
- The Pydantic AI Harness port that no command used is deleted: the shell, filesystem, memory, planning, compaction, sub-agent, docs, repo-context and conversation-search modules of `devops_cli.ai.harness`, the coder, researcher, Macroscope and Playwright agents, and the capability clones in `devops_cli.ai.agents.capabilities` that copy what `pydantic_ai.capabilities` already ships. `devops ai harness` is unchanged, the `Skills` capability that nothing built goes with them, and `HarnessExecutionError` and `MemoryOperationConflictError` are gone with their only caller ([#1836](https://github.com/dan-petty/devops-cli/issues/1836)).
- Tree-sitter alone parses a file's symbols: the regex parser that stood behind it (`devops_cli.ai.ast.fallback`), `devops_cli.ai.ast_stream`, `devops_cli.ai.ast_cache`, `devops_cli.ai.rag.cache`, `CrossEncoderReranker` and `budget_diff_chunks` are deleted, about 1,500 lines with the tests that only exercised them. Over the repository's own Python, Markdown and HCL files the regex parser decided none of the 1,971 files. Over about 59,000 third-party files it decided 65 (0.11%): 55 of 3,505 Rust files, 8 of 473 TypeScript files and 2 shell files, items inside Rust `macro_invocation` bodies, `.d.ts` function signatures and mocha `it()` calls, which now have no symbols. `devops ai ast parse --json` no longer prints a `parse_engine` key, and a symbol, here and in `devops ai ast graph --json`, no longer carries `docstring`, which only the regex parser ever filled and which was always empty after it (pre-1.0, no shim). A sample validation report no longer names a language read by the regex fallback, and drops the per-file `parser` and the `parsers` count, which repeated `ast_language`, with the Parsers column of `devops review samples validate` ([#1839](https://github.com/dan-petty/devops-cli/issues/1839)).
- The dependency-manifest parsers (`extract_dependencies_from_text` and its pip, pyproject, package.json, Cargo and go.mod extractors), the Vault Transit helpers (`transit_encrypt`, `transit_decrypt`), `CallableProvider`, `ProcessExecutionPipeline` and the `cli_command_handler` decorator are deleted: nothing called them since the review began scanning lockfiles with osv-scanner ([#1841](https://github.com/dan-petty/devops-cli/issues/1841)).
- The dead layer over pydantic-ai is deleted: the re-export modules for its exceptions, profiles, result, run, concurrency, template and direct APIs and the LangChain adapter, the hand-written provider classes and `get_provider` registry beside `create_pydantic_ai_provider`, `LLMClient.direct_request`, `direct_stream` and their sync forms, `model_request` and `model_request_sync`, the bridge's agent factories and workflow helpers with the token governor, the wrappers around single library calls in the tools, toolsets, settings, retries, format-prompt and output helpers, the pydantic-ai exception subclasses and aliases that no code raised or caught, and the `pydantic-graph` direct dependency, which pydantic-ai still installs. Code that needs one of them imports it from pydantic-ai ([#1852](https://github.com/dan-petty/devops-cli/issues/1852)).
- This change deletes the web fetch tool and its renderer for untrusted pages. It also deletes the DuckDuckGo scraper, the wrappers for Exa, X search and image generation, and the prompt-injection guardrails. The dependencies `markdownify`, `beautifulsoup4` and `soupsieve` go with them. Nothing called this code after the harness agents went away. `devops_cli.ai.common_tools` keeps `tavily_search`, which `devops roadmap refine` uses ([#1854](https://github.com/dan-petty/devops-cli/issues/1854)).
- The 11 tests that asserted deleted names stay deleted are gone from `tests/test_codebase_hygiene_and_shims.py`. A refactor that deletes code no longer edits that file. Git history records what was deleted. A trial of `vulture` as a dead-code check left 720 findings on `src` after it ignored the framework decorators and callbacks. A check for functions and methods only left 26 findings, and two of them are live framework hooks. That check needs 12 decorator patterns and 7 name patterns first, so `vulture` is not adopted. The test that every private function in `security/` has a caller stays ([#1871](https://github.com/dan-petty/devops-cli/issues/1871)).
- The change deletes the GitHub tab and the AI Review tab of `devops dashboard`. The dashboard now has four domain tabs (Kubernetes, Docker, Telemetry and Valkey Cache) and the Logs tab. `--tab 4` opens Valkey Cache. The GitHub tab never loaded, because its queries asked GitHub for a field that does not exist. It also polled GitHub every 60 seconds. Use `gh-dash` for the pull request queue, `devops gh rate-limit` for the quota and `devops gh runs view <run> --log-failed` for the log of a failed run. Use `devops review findings --details` to read the findings of a review session. No command replaces the session list of the AI Review tab. `devops dashboard --summary` still shows the AI Review Findings panel ([#1883](https://github.com/dan-petty/devops-cli/issues/1883)).

### Fixed
- Checkouts and worktrees nested inside an unrelated git repository (such as a dotfiles repository at `$HOME` or an outer workspace) resolve to their own repository's main worktree, rather than mistakenly resolving to the enclosing outer repository (#617).
- `devops ai gateway tune` attaches one sweep container to the gateway pod for a whole run, where it used to attach another for every deployment once the first had exited. The container's `sleep` now covers the exec budget of every deployment in the run, where a fixed hour could end in the middle of a sweep, and a container that exits during the run stops the run with an error naming it instead of being replaced ([#796](https://github.com/dan-petty/devops-cli/issues/796)).
- A group-analysis reply that does not parse or fails a G10 check is no longer cached or served from the cache: the job makes one model call per group and records the reason, where an empty reply used to be sent up to five times and an unusable one was replayed for 7 days ([#1013](https://github.com/dan-petty/devops-cli/issues/1013)).
- A reply that ends asking for a tool call is no longer cached, and each cache entry records the backend and model that answered, which a hit returns ([#1013](https://github.com/dan-petty/devops-cli/issues/1013)).
- Semgrep no longer sends metrics, checks its version or downloads rules when a review or `devops scan` runs it. Every Semgrep scan that devops-cli starts now carries `--metrics off` and `--disable-version-check`. The rule pack of devops-cli always runs, with whatever config the scan names ([#1144](https://github.com/dan-petty/devops-cli/issues/1144)).
- `devops review rules fetch` caches the registry ruleset `p/default`. It downloads the ruleset again only when its ETag changes. Reviews, `devops scan sast`, `devops scan report` and the agent tool read the cache offline. A missing cache is a coverage gap, and the gap names the fetch command. The file `profile.json` records the digest as `semgrep_registry_digest` ([#1144](https://github.com/dan-petty/devops-cli/issues/1144)).
- A review lists the files that Semgrep did not scan. A file of the review that `paths.scanned` of Semgrep does not hold is such a file. The Coverage section of review.md shows it as `not scanned(...)`. The Static Analyzers table shows a coverage gap and the count of such files ([#1144](https://github.com/dan-petty/devops-cli/issues/1144)).
- A webhook whose signature header carries non-ASCII text is refused with 401 instead of failing the request ([#1386](https://github.com/dan-petty/devops-cli/issues/1386)).
- An item whose refined body would pass the 65,536-character limit is recorded after its first try, and an item whose model reply never fits the schema or is refused is recorded after its second try on the same body, so neither takes a place and spends model calls in every round until a person edits it. A timeout or a dropped stream records nothing ([#1526](https://github.com/dan-petty/devops-cli/issues/1526), [#1539](https://github.com/dan-petty/devops-cli/issues/1539)).
- The check for a second `sgconfig.yml` and the check of the covered source files in `tests/test_architectural_invariants.py` count only the files that git tracks. A nested worktree under `.claude/worktrees/`, or scratch under `.data/`, no longer fails `devops ci` or the commit hook. A project that is not a git repository fails the check and does not pass on an empty listing ([#1787](https://github.com/dan-petty/devops-cli/issues/1787)).
- The release job stops, naming both commits, when the tag for the version it would publish already exists on another commit, so a push to `main` that still names the last release's version can no longer republish that release's assets or rebuild its images ([#1805](https://github.com/dan-petty/devops-cli/issues/1805)).
- A test no longer fails with `None` because an earlier test in the same pytest worker ran a nested pytest session that loaded `pytest-randomly`: the session's numpy import was undone while its C extension stayed loaded, and the next import of numpy in that worker raised "cannot load module more than once per process" ([#1807](https://github.com/dan-petty/devops-cli/issues/1807)).
- Tempo starts again on chart 3.1.0 (Tempo 3.1.0): the values no longer replace the chart's config with a Tempo 2 copy whose `compactor` and `ingester` blocks Tempo 3 rejects, so the chart's own config is used ([#1813](https://github.com/dan-petty/devops-cli/issues/1813)).
- The eBPF profiler pod on the node that runs the most pods is no longer OOMKilled every few minutes: the `alloy-profiles` memory limit is 1024Mi, up from 512Mi ([#1815](https://github.com/dan-petty/devops-cli/issues/1815)).
- Opening the spend ledger from several threads at once no longer fails with "database is locked": the switch to WAL, which SQLite refuses to wait for, is made once and one thread at a time, so parallel first AI calls record their spend ([#1820](https://github.com/dan-petty/devops-cli/issues/1820)).
- Two tests no longer assert elapsed wall-clock time, so a busy machine no longer fails the gate on them. The knowledge base metadata test dropped its limit of one second, because the hermetic floor already proves that the test is offline. The dashboard test for quitting while a log stream is silent now asserts that the application shut down before the stream was released, and it fails if quitting waits for the stream thread ([#1825](https://github.com/dan-petty/devops-cli/issues/1825)).
- `devops ai ast parse --query` runs the tree-sitter S-expression it is given: the query `(call function: (identifier) @callee)` prints the callee, with the capture's name as `kind`, where it printed the enclosing function. A query tree-sitter cannot compile, `(((` for one, exits 1 with `Invalid tree-sitter query` where it exited 0 and printed every symbol of the file ([#1839](https://github.com/dan-petty/devops-cli/issues/1839)).
- `devops roadmap refine --dry-run` makes no GitHub requests and no model calls, returning the planned requests with placeholders and leaving the store unread ([#1867](https://github.com/dan-petty/devops-cli/issues/1867)).
- The test that a timeout stops a whole process group no longer fails on a busy machine. It now starts its timeout after the child and its grandchild exist, and it stops waiting on the start of two Python interpreters within 0.6 seconds ([#1888](https://github.com/dan-petty/devops-cli/issues/1888)).
- The published devcontainer image `ghcr.io/dan-petty/devops-cli/devcontainer` holds its Dev Container Features and the user `vscode` again. So a repository that names only the image with `"remoteUser": "vscode"` opens. Since v0.2.35 the release built the Dockerfile alone, and the Dev Containers CLI stopped with `unable to find user vscode`. Now the Dev Containers CLI 0.89.0 from `tools.lock` builds `.devcontainer/devcontainer.json` for `linux/amd64` and `linux/arm64` and pushes the image by digest. A second job starts that digest as `vscode` without write permissions. Only then does the release attest and tag the digest. The pull request check runs the same two actions against a registry on the runner and publishes nothing. `devops install-tools` and post-create install the CLI as `devcontainer` ([#1895](https://github.com/dan-petty/devops-cli/issues/1895)).
- The tests that a second Ctrl-C, SIGTERM or SIGHUP cannot skip the SIGKILL of `devops ci test` no longer fail on a busy machine. The fake program now records SIGINT and SIGTERM before it writes its pids. Before, the program lost a signal that came right after it wrote its pids, and the test failed with `interrupted` false ([#1913](https://github.com/dan-petty/devops-cli/issues/1913)).
- `.gh-dash.yml` refreshes gh-dash every 60 minutes and starts it with the preview closed. The computed cost is now 7 GraphQL points at start and 5 points an hour. With a refresh every 15 minutes and the preview open, it was 9 points at start and about 28 points an hour. The token has a budget of 5,000 points an hour, and AI agents use the same token. The `p` key opens the preview. `docs/DEVCONTAINER_USAGE.md` states the costs, the source of each number and how to count the requests from `debug.log`, and `tests/test_gh_dash_config.py` pins the two values ([#1918](https://github.com/dan-petty/devops-cli/issues/1918)).
- `devops ssh list` shows only the managed keys of the project prefix. Before, it showed the keys of all projects when the prefix matched no key. The new option `--all` shows the keys of all projects ([#1920](https://github.com/dan-petty/devops-cli/issues/1920)).
- `devops ssh register`, `rotate` and `status` use only a key of the project prefix. When no such key exists, they say so and point to `devops ssh generate`. Before, they used the newest key of another project. `register` uploaded that key to GitHub, and `rotate` rotated it ([#1920](https://github.com/dan-petty/devops-cli/issues/1920)).
- A hyphen and an underscore in a key prefix are now the same character. The prefix `devops-cli` matches the key `devops_cli-id_ed25519-20260831` in every `devops ssh` command and in `devops devcontainer post-start` ([#1920](https://github.com/dan-petty/devops-cli/issues/1920)).
- `devops ssh register` names a key on GitHub with the file name of the key when the key has a prefix. Before, it added the project prefix a second time when the two prefixes spelled the separator in different ways ([#1920](https://github.com/dan-petty/devops-cli/issues/1920)).
- The DevContainer image smoke test runs each platform by the digest of its own manifest in the image index. Before, it ran `linux/amd64` and `linux/arm64` by the one index digest, and the classic image store of the runner stopped the second platform with `cannot overwrite digest`. The check of the release pull request failed, and the `devcontainer-smoke` job of `release.yml` would have stopped the attestation and the tags of the image ([#1949](https://github.com/dan-petty/devops-cli/issues/1949)).

### Security
- The OpenTelemetry packages move to 1.45.1 (contrib 0.66b1), which clears GHSA-xcq7-p3pf-p88h (unbounded tracestate parsing in `opentelemetry-api`), and `logfire` moves to 5.2.0, the first release that accepts them. `gitpython` moves to 3.2.1, which clears GHSA-83vg-56qc-22m7 (a submodule's `.git` path checked only after the clone). Both advisories were published on 2026-10-22 and failed the `audit` row of every `devops ci` ([#1899](https://github.com/dan-petty/devops-cli/issues/1899)).

## [0.2.38] - 2026-10-21

### Added
- Add `ServiceMonitor`s and exporters for Argo CD (`controller`, `server`, `repoServer`, and `redis` exporter), `llm/valkey` (`redis-exporter` sidecar), and `registry` (Distribution debug Prometheus endpoint on port 5001), with `homelab-services` alerts (`ArgoCdApplicationOutOfSync`, `ArgoCdApplicationUnhealthy`, `ArgoCdAutoSyncDisabled`, `ArgoCdSyncOperationStuck`, `CloudflareTunnelDegraded`, and `ValkeyCacheErrors`) (#551).
- Add the `CoreDNS` Grafana dashboard (`k8s/monitoring/dashboards/coredns.json`, `uid: devops-coredns`), CoreDNS exporter metric capture (`tests/fixtures/metrics/coredns.yaml`), and `CoreDnsServfailResponses` alert rule (`k8s/monitoring/prometheus-values.yaml`) over `job="integrations/kubernetes/kube-dns"` (#822).
- Added `constructs` CI quality gate powered by `ast-grep-cli==0.51.0` enforcing 12 structural AST rules against hand-rolled URL, scheme, domain suffix, and IP address manipulation across the codebase with a suppression ceiling of 0 ([#1107](https://github.com/dan-petty/devops-cli/issues/1107)).
- Configured Ruff `TID251` (banned-api) to forbid legacy `socket.inet_*` functions in favor of `ipaddress.ip_address` ([#1107](https://github.com/dan-petty/devops-cli/issues/1107)).
- Dependency advisories and package inventory come from `osv-scanner` 2.6.0 over repository lockfiles offline with a 24-hour TTL snapshot database. Review findings carry `AdvisoryAnchor` models with `purl@locked-version` and snapshot digests, severities are preserved directly from advisories without defaulting to HIGH, and CycloneDX 1.5 inventories are stored in environment facts while missing lockfiles report coverage gaps. Network intelligence lookups via Shodan and Cloudflare Radar are opt-in ([#1146](https://github.com/dan-petty/devops-cli/issues/1146)).
- Review analysis links related findings across groups using deterministic cross-group keys (CWE, rule family, symbol-graph component, purl, and manifest source) in a correlation table in `analysis.json` and `review.md`. G10 verification enforces that any "same root cause" statement only links findings sharing a correlation key, and a review-level remediation plan orders all admitted findings (introduced first, then severity rank, then file path) and groups related resources ([#1148](https://github.com/dan-petty/devops-cli/issues/1148)).
- Knowledge-base manuals declare version constraints (`applies_to`), authoritative `sources`, and `reviewed` date front-matter across tools, topics, and library manuals.
- Ground group review explanations in environment-matched knowledge-base manuals keyed by `kb:<path>@<sha>`, prioritizing official rule docs and reporting mismatched or undated manuals under reference coverage drift.
- Added `--no-group-analysis` CLI flag across `devops review` subcommands (`path`, `branch`, `pr`) ([#1151](https://github.com/dan-petty/devops-cli/issues/1151)).
- `devops k8s deploy-stack --stack llm` warns about every GPU node no Ollama tier accepts, naming the node and the label it lacks with the `kubectl label node` command that sets it, says no Ollama pod will schedule when no node satisfies any tier, and says so when it cannot read the nodes. It reads the nodes before the Argo CD early return, so it warns on an Argo CD-managed cluster too, and it never stops the deploy. The accepted values are read from `ollama-profiles.yaml`, and the README's GPU placement section lists them per tier ([#1367](https://github.com/dan-petty/devops-cli/issues/1367)).

### Changed
- Refactored `DocGenerator.write_all_docs`, `check_docs`, and `sync_readme` to consume a pre-generated `{path: content}` doc set seam, avoiding redundant module introspection.
- Cached introspected command groups and pre-rendered README command matrix content so `DocGenerator.check_docs` introspects live command groups only once.
- Refactored doc mechanics tests `test_write_and_check_docs` and `test_doc_generator_write_all_and_check` to run on a two-entry fixture without module introspection or argv validation, dropping test execution time from ~45s to sub-second.
- Added unit test `test_one_check_docs_call_introspects_once` verifying `check_docs` performs live group introspection at most once.
- Replaced hand-rolled network, scheme, URL authority, and domain matching across `src/` with official standard library and ecosystem parsers (`ipaddress`, `urllib.parse`, `httpx2`, `dns.name`, `jeepney`) ([#1107](https://github.com/dan-petty/devops-cli/issues/1107)).
- Migrated default homelab IP configuration and TLS SAN certificate request models to use `ipaddress` objects natively ([#1107](https://github.com/dan-petty/devops-cli/issues/1107)).
- Consolidated the Kubernetes monitoring stack onto `grafana/k8s-monitoring` and native chart features: enabled `integrations.alloy`, `integrations.grafana`, Pyroscope `serviceMonitor`, `profiling` (`alloy-profiles` eBPF + `pprof` to `destinations.localPyroscope`), Argo CD chart `ServiceMonitor`s (`controller`, `server`, `repoServer`, `redis`), `llm/valkey` (`redis-exporter`) and `registry` pod-annotation scraping, added the CoreDNS dashboard (`devops-coredns`) and pipeline/service health alert rules (`AlloyRemoteWriteSamplesFailed`, `AlloyLogEntriesDropped`, `PodLogsNotShipped`, `PyroscopeQueryErrors`, `homelab-services`), disabled `loki-canary` and Pyroscope's bundled Alloy subchart, scoped Grafana sidecars/RBAC and Loki ingress peers, aligned stack dashboards with captured exporter metrics, and moved the `llm-gateway` `ServiceMonitor` to `k8s/llm/gateway/servicemonitor.yaml` via the post-Helm `deploy-stack` table (#1128).
- Decoupled finding-group model analysis from personas, allowing group analysis to synthesize scanner findings independently ([#1151](https://github.com/dan-petty/devops-cli/issues/1151)).
- Review commands now instantiate LLM clients only when a model-driven stage is enabled (`ReviewStageFlags.needs_model()`) ([#1151](https://github.com/dan-petty/devops-cli/issues/1151)).
- Relocated review diff parsing and target path resolution to dedicated modules (`diff.py` and `targets.py`), retaining interactive personas strictly for `devops ai chat` ([#1151](https://github.com/dan-petty/devops-cli/issues/1151)).
- Enforce a default-deny hermetic test floor across process, network (TCP, DNS, and `AF_UNIX`), and keyring edges with `<edge> edge reached without a fake: <target>` errors, `@pytest.mark.live` and `@pytest.mark.unreachable` markers, `config` and `cli` fixtures, and automatic reset of all process-wide state in `src/devops_cli/` after every test (#1310).
- Added `devops_cli.core.clock` (`sleep`, `async_sleep`, `monotonic`), `ClockFake` and the `clock` fixture backed by `time-machine` (`tick=False`), routed `create_retry_transport`, `create_async_retry_transport` and `GitHubRateLimiter`'s burst limiter through the clock seam at call time, and migrated `tests/test_pydantic_ai_retries.py`, `tests/test_github_rate_limiter.py`, `tests/test_ai_request_priority.py` and `tests/test_server_service.py` off `time.sleep` patches and wall-clock elapsed assertions (#1320).
- The dashboard tests run with Textual's animations off, list a doubled Docker engine instead of the workstation's own, and wait for conditions instead of fixed pauses. With base and change run side by side under the same load, the dashboard file went from 50s to 8s and the reactive file from 174s to 133s, and every behaviour is still checked ([#1339](https://github.com/dan-petty/devops-cli/issues/1339)).
- `deploy-stack` reads the cluster's nodes through one reader that reports a failed read, which the unready-node check shares.
- Documented in `AGENTS.md` and `docs/SDLC.md` that the pre-push hook's `uv run devops ci` is the gate run and reuses content-addressed verdicts when unchanged, avoiding redundant 200s–900s CI runs. Added test coverage in `tests/test_ci_cache.py` proving verdict survival across `git add` and `git commit` and invalidation on amend ([#1663](https://github.com/dan-petty/devops-cli/issues/1663)).
- Updated the `structural-invariants` pre-commit hook to invoke the pure-standard-library AST metrics module directly (`python3 -P src/devops_cli/core/code_metrics.py`) and set `require_serial: true`. This executes the hook across all staged files in a single fast process without virtual environment synchronization or OSV malware network queries, reducing hook run time to under 0.1 seconds ([#1667](https://github.com/dan-petty/devops-cli/issues/1667)).
- Optimized CI test suite and quality gate execution times to meet release performance budgets: eliminated real scanner invocations via recorded scanner doubles, replaced textual UI sleeps with reactive condition waits, measured startup import argvs once via shared probes, isolated devcontainer tests from real installers and sudo, balanced parallel xdist workers with `--dist worksteal`, and compiled environment bytecode once across CI runners ([#1725](https://github.com/dan-petty/devops-cli/issues/1725)).
- Enforced hermetic test invariants: session fixtures fail any test attempting network egress, connections to unstarted localhost services, or execution of real scanner binaries ([#1725](https://github.com/dan-petty/devops-cli/issues/1725)).
- The devcontainer post-create and post-start tests no longer start Claude Code's real installer, a uv sync of the review tools, kubectl or sudo. On the GitHub runner that removes about 55 seconds of test time and about 1.1 GB of downloads from every CI run ([#1731](https://github.com/dan-petty/devops-cli/issues/1731)).
- Tests render each committed Kubernetes kustomization once per test process and share the render. `docs/TESTING.md` and ADR 0007 now list kubectl's offline renderers, `kubectl kustomize` and `kubectl patch --local`, with git as tools tests run for real ([#1732](https://github.com/dan-petty/devops-cli/issues/1732)).
- The startup-import checks start one interpreter per command line instead of re-measuring nine of them, so the file starts 54 interpreters instead of 63 with every check kept ([#1733](https://github.com/dan-petty/devops-cli/issues/1733)).
- The test suite runs with pytest-xdist's `worksteal` scheduling, so the last worker finishes closer to the others, and the gate starts Bandit under `nice` so it yields CPU to the test row. Replaying a full run's test times predicts about 42 seconds less on the 4-worker CI runner ([#1734](https://github.com/dan-petty/devops-cli/issues/1734)).
- CI's test run keeps the environment the workflow built: the gate's child processes keep uv's settings, so the test row no longer rebuilds the virtual environment and re-downloads every package, and the CI toolchain compiles its bytecode once instead of in every pytest worker. A narrowed local test run starts in about 3 seconds instead of 6-7, because the test bootstrap no longer imports pydantic-ai at every start ([#1735](https://github.com/dan-petty/devops-cli/issues/1735)).
- No test connects to a localhost service it did not start. Tests that need a model use the shared model fake, a service that is down is a loopback port the test binds and never serves, telemetry export and the Valkey cache go to a refusing port bound for the run, and a guard fails any test that connects to a loopback port the test process does not bind. Six of the affected test files take 20 seconds less ([#1741](https://github.com/dan-petty/devops-cli/issues/1741)).
- Invariant and architectural tests share a single session-scoped parse of the source and test trees per test process through `tests.support.trees`. Invariant tests no longer re-parse the full repository on each run, bringing every test well under the 5-second ceiling ([#1749](https://github.com/dan-petty/devops-cli/issues/1749)).

### Removed
- Deleted the candidate-generating persona review stage and reviewer persona flags from `devops review`, along with the legacy review segment engine, `chunker.py`, and review-time RAG context injection ([#1151](https://github.com/dan-petty/devops-cli/issues/1151)).
- Removed repository-level `.devops/review.md` prompt conventions, verification note kinds, and obsolete hallucination catalog remnants in favor of deterministic rule packs and `.devops/review.toml` suppressions ([#1151](https://github.com/dan-petty/devops-cli/issues/1151)).
- The 36 commented-out `gpu.architecture` and `gpu.family` lines left in six Ollama DaemonSets by the vLLM/Ollama split ([#1367](https://github.com/dan-petty/devops-cli/issues/1367)).

### Fixed
- The OpenTelemetry collector starts after the Tempo it exports traces to, so a fresh deploy no longer logs a burst of `connection refused` against Tempo that reads like an outage: `deploy-stack` installs `tempo` before `otel-collector`, and the `otel-collector` Argo CD Application syncs in a later sync wave than `tempo` ([#409](https://github.com/dan-petty/devops-cli/issues/409)).
- OpenTelemetry collector remote-writes metrics directly to Prometheus in one hop, bypassing the two-hop Alloy receiver path and preventing batch drops from out-of-order samples.
- Configured Prometheus server TSDB out-of-order time window to 10m to tolerate jitter and late samples safely.
- Cleaned unused collector receivers (Jaeger, Zipkin, Prometheus scrape), disabled unused container ports, removed debug exporters, and removed redundant memory limiter percentages.
- Remove the `except StopIteration, IndexError` fallback from `_fetch_commit_statuses_from_rest` so `check_verdict` fails closed when the runner raises instead of swallowing under-scripted test mocks (#1350).
- Pre-populated `TIKTOKEN_CACHE_DIR` (`cl100k_base` and `o200k_base`) at image build in `Dockerfile` and `.devcontainer/Dockerfile`, resolved pre-populated tiktoken cache directories in `devops_cli.ai.context_budget` without network downloads when the cache directory is missing or empty, and logged a `WARNING` naming the cache directory on fallback (#1421).
- Upgrade `.github/actions/setup-toolchain/action.yml` from `actions/cache@v4.3.0` (Node 20) to `actions/cache@v6.1.0` (Node 24) and add a `save-uv-cache` input so only `Static Analysis` saves the `setup-uv` cache on `push` and `pull_request` events (#1495).
- Closed SQLite connections opened directly in `SpendLedger` test suites (`tests/test_ai_served_by.py`, `tests/test_ai_spend_dispatch.py`, `tests/test_ai_spend_ledger.py`, `tests/test_review_profile.py`, and `tests/test_telemetry_instruments.py`) with `contextlib.closing`, suppressed `DeprecationWarning` emitted when `PackageIntrospector.introspect_package` reads deprecated attributes of an inspected library, and upgraded `starlette` in `uv.lock` (`1.6.0` -> `1.9.0`) to eliminate `anyio.abc.BlockingPortal` deprecation warnings (#1497).
- Wrap FastMCP tool functions exposed by `get_mcp_agent_tools()` in `fastmcp.server.dependencies.without_injected_parameters` and resolve awaitable tool results in `Tool.execute()` so `PydanticAgent` tool schemas exclude FastMCP's injected `ctx` parameter without emitting `PydanticJsonSchemaWarning` and execute cleanly without an MCP session (#1498).
- The test suite no longer starts a real Semgrep, Gitleaks or Bandit, so Semgrep no longer downloads its `p/default` rules from inside a test: the six review tests that ran them answer from runs recorded from the real tools at their locked versions, and take about 5 s together instead of 50 s. A test that would start a real gh or security scanner now fails, naming the program (#1666).
- Reduced test process execution times for hung process group tests and GitHub session-exit subprocesses to well under 5 seconds by lowering the hung-run timeout bound and removing transitive heavy package imports during network egress IP classification ([#1748](https://github.com/dan-petty/devops-cli/issues/1748)).

### Security
- Updated `certifi` to 2026.10.19 to address GHSA-6q48-6c7w-9gw2 ([#1748](https://github.com/dan-petty/devops-cli/issues/1748)).
- The lockfile moves `virtualenv`, a dependency of `pre-commit`, from 21.14.1 to 21.14.12, which fixes four advisories (among them GHSA-vxj4-q4g9-crj7) that failed the audit check of every pull request ([#1790](https://github.com/dan-petty/devops-cli/issues/1790)).
- The service image installs `gh` 2.102.1, built with Go 1.27.3, which fixes CVE-2026-111943 (HIGH, `crypto/x509`) in the Go standard library of the `gh` binary that Trivy flagged in the image ([#1800](https://github.com/dan-petty/devops-cli/issues/1800)).

## [0.2.37] - 2026-10-20

### Added
- `devops roadmap reprioritize` sweeps open P0 and P1 backlog items into open planned releases holding fewer than 16 items (`release_cap + release_slots`), in `_Ranks.first` order with the `priority` reason comment. A backlog P0 meeting a full release displaces the lowest-ranked unimplemented P3 item in it, which moves to the next release with room or to the backlog; a P1 never displaces anything and moves to the next release with room. When every planned release is full, reprioritize creates the next patch release and places the item there. Items a person took out of a release stay in the backlog. At a start, New and Blocked P0/P1 items go to the next planned release instead of the backlog (#882).
- The GitHub session sends REST requests itself, through gidgethub over the egress factory's client ([ADR 0006](docs/adr/0006-github-session-requests-go-through-gidgethub.md)): `GitHubSession.rest()` and `paginate()`, which follows GitHub's `Link: rel="next"` one page at a time, stops sending when its reader stops and fails closed on a page that holds no list or a listing past the page cap. Every request is paced and charged on the identity's one ledger, the one `run_gh` uses, is sent only to GitHub's API origin, is retried on a rate limit and on a read's 5xx, and a repeated GET of a `rest()` read, or of a listing page that links a next one, is sent with the ETag the session kept, so a 304 answers it from memory ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- `GitHubScopeError`, `GitHubNotFoundError` and `GitHubUnreadError`, which the session classifies from an HTTP answer's status and headers. A failed gh command is classified from its exit status and stderr by one table in `config/constants.py`, into a rate limit, a missing scope or a refused login ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- `DEVOPS_CLI_AI_GATEWAY_URL` environment variable and `ai.gateway_url` configuration option to direct the AI client at an authenticated LLM gateway endpoint.
- `DEVOPS_CLI_AGENT_GRANT` environment variable for agent sessions, with bounded grant-aware 401 authentication hints that suppress generic API key setup reminders when an expired or revoked grant is in use.
- Claude Code deny rules protecting ambient developer credentials (`~/.claude/settings.json`, `.claude/settings.local.json`, and `~/.kube/**`) during agent sessions.
- Read-only agent identity under GitOps in `k8s/agents/`: namespace `agents` enforcing restricted Pod Security Standards, ServiceAccount `devops-agent` with `automountServiceAccountToken: false`, and ClusterRoleBinding `devops-agent-view` bound to the read-only `view` ClusterRole.
- Argo CD Application `agents` under project `homelab`, orphan-resource ignore rules for transient session secrets (`agent-grant-*`), and native `devops k8s deploy-stack` integration for agent manifests.
- `tests/support/` holds what tests share, and the root conftest's one `pytest_plugins` entry, `tests.support.bootstrap`, isolates HOME and then registers every submodule and subpackage under it as a plugin, so a fixture added there reaches every test with no conftest edit (#1312). A run fails on a support module whose fixture or hook its source does not show, on a test module or conftest under `tests/support/`, and on a support module imported before assertion rewriting was set up.
- Test modules read the repository root and their test data from `tests/support/paths.py` (`REPO_ROOT`, `TESTS_ROOT`, `FIXTURES` and `GOLDEN`), so a module reads the same paths at any depth. A check fails a module under `tests/` that reads its own `__file__` outside `tests/support/` or imports a test module or a conftest, naming each `path:line`. It runs in the full gate, `uv run devops ci` and the pre-push hook; a narrowed `devops ci test` runs it only when given its module.
- Shared builders for test data in `tests/support/builders.py`: `make_finding`, `make_verdict`, `make_item`, `make_release`, `make_candidate` and `make_changelog_fragment`, each building through the type's own constructor or parser, so an override the type refuses raises the type's own error. `parse_changelog_fragment` holds the checks the changelog fragment reader makes, and the reader and the builder share it. syrupy 6.1.1 joins the dev dependencies for snapshot tests.
- Offline deterministic Argo CD build gate in `devops release prepare --create-pr` (and `cut_release`), building all repository-managed `Application` manifests via Kustomize from an isolated `git archive` snapshot at the release head before cutting a release (#1343).
- Strict template domain placeholder safety validation across all rendered manifests and Helm value files, ensuring placeholders appear only in authorized host fields of homelab applications (`devops`, `ingress`).
- Live, non-blocking Argo CD application diff and override reporting using `argocd app diff --grpc-web`, verifying live cluster diffs and surfacing any template domain placeholder hosts lacking active live overrides alongside their remediation command (`devops k8s deploy-stack --stack <stack>`) (#1343).
- A release pull request gets a set number of Copilot review passes: `release_copilot_passes` in `.github/roadmap.toml`, 2 by default, counts every Copilot review submitted on it, whoever asked for it, and a pass running or requested and not yet started. `devops pr copilot-pass [<number>] [--dry-run]` requests a pass with `gh pr edit --add-reviewer @copilot` only on the open release pull request while its passes are below the budget; otherwise it requests nothing and exits 1, saying `Copilot budget spent: N of N passes` once they are spent (#1345).
- `devops pr threads file-issues <pr> [--keep <thread-id>] [--confirm] [--dry-run]`, which a person runs, files each unresolved review thread of the open release pull request as a follow-up issue with no milestone, labelled `source/agent` when Copilot started the thread, quoting the thread in a fence so no mention notifies and no issue reference links, then replies in the thread naming the issue and resolves it. Without `--confirm` it writes nothing, and a `--keep` id that names no unresolved thread stops it before any write. A rerun opens no second issue for a thread: it resolves a thread whose reply from the same account names its issue, and finds by the thread's link the issue it opened for a thread whose reply failed (#1345).
- `RELEASE_CYCLE.md` Step 3 states the stop rule: once the budget is spent, a remaining comment blocks the release only if it is a regression the release introduces, and every other one becomes a follow-up issue (#1345).
- The `devops_cli_ai_gateway_slot_wait_seconds` histogram, by outcome (`ok` or `timeout`), and an `ai.llm.gateway_slot` span record how long a gateway chat call waited in the process for a backend slot. A call's `llm.wall_seconds`, its time to first chunk and its spend's duration start once it holds the slot, so a review waiting for slots no longer looks like slow inference (#1354).

### Changed
- Dropped Status, Milestone, and Priority fields from task files per ADR 0001, removed un-implemented task files from the repository, and updated agent instructions so task files are authored only by delivering pull requests.
- The pull request diff, the SSH signing key, the issue, milestone, timeline, review, check-run, file and repository listings, and the roadmap store's REST listings are read through the session instead of `gh api --paginate` or their own httpx2 clients, so a malformed or failed page is a read failure instead of a shorter list, and a poll stops at its first entry older than its cutoff ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- `devops gh api --paginate` hands gh `--paginate`, `--slurp`, `--jq` and `--template` as given, under `DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS` ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- A failed quota refresh raises the unauthenticated error for a refused token or gh's exit status 4, the rate-limit error for a rate limit, and the unread error for anything else, a timeout included; `devops gh issues list` and `devops roadmap intake` report each without a traceback ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- `devops roadmap intake --plan`'s spend line counts every request the identity's ledger paces, gh commands and session requests alike ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- The gh-output table holds only what gh writes for a GitHub failure: the project-scope wordings, which neither gh nor go-gh writes, and `authentication required`, which gh writes only in an authenticating proxy's `Proxy Authentication Required`, name no class any more ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- The FastMCP tool bridge is now dynamically generated from Typer/Click command metadata driven by `CONST_MCP_EXPOSURE_TABLE` (146 commands), eliminating hand-written argv construction wrappers in `server.py` (#997).
- Exactly 5 tools remain hand-written (`hydrate_tool_domain`, `security_intel_package`, `security_intel_network`, `scan_uv_audit`, `k8s_tempo_info`), and dead functional handlers in `dispatcher.py` (`register_handler`, `_functional_handlers`, `_check_functional_handlers`) and test-detecting branches in `server.py` are removed (#997).
- Tool names derive canonical names from `"_".join(command_path).replace("-", "_")` with zero legacy shims (#997).
- Parametrised and exhaustive coverage tests verify tool schemas against Click command parameters and enforce complete coverage across the CLI command tree (#997).
- Unified the AI model edge under a single shared seam (ADR 0007), providing an in-memory `ModelFake` implementing `pydantic_ai.models.Model` and `LLMClient` duck typing, accompanied by a contract suite in `tests/test_model_contract.py` and fixture `model_fake` in `tests/conftest.py` (#1001).
- Consolidated client creation into `get_llm_client` and `build_llm_client` in `devops_cli.ai.client.factory` with override support, routing all inline `LLMClient` constructions across `src/` through the factory, and removing `config/settings.py:get_llm_client`.
- Injected egress factory HTTP clients (`new_async_http_client`) with bounded timeouts and SSRF validation into Pydantic AI providers, and unified direct spend tracking in `devops_cli.ai.direct` across synchronous, asynchronous, and streaming requests.
- Migrated test suites across CLI commands, agents, prewarm, chaos model, instruction generator, and roadmap refine away from internal `LLMClient` monkeypatches to the shared `model_fake` fixture.
- Network reference reports, Shodan InternetDB and Cloudflare Radar records and `check_threat_intel` replies move these blocks between classes (#1174). From "Documented Example" to local: 0.0.0.0/8 (the unspecified 0.0.0.0 itself is still rejected), 100.64.0.0/10, 192.0.0.0/24 except 192.0.0.9 and 192.0.0.10, 192.88.99.0/24, 240.0.0.0/4, 255.255.255.255, 100::/64, 2002::/16 and the rest of 2001::/23, Teredo 2001::/32 and the deprecated ORCHID 2001:10::/28 among them. From "Documented Example" to public, so Shodan InternetDB may be asked about them: 192.0.0.9, 192.0.0.10, 2001:1::1, 2001:1::2, 2001:3::/32, 2001:4:112::/48, 2001:20::/28 and 2001:30::/28, which IANA lists as globally reachable. From public to local: site-local fec0::/10 (RFC 3879) and the IPv4-mapped spelling of 192.88.99.0/24 (`::ffff:192.88.99.1`). From local to "Documented Example": 3fff::/20 (RFC 9637) and the IPv4-mapped spelling of documentation and benchmarking space (`::ffff:192.0.2.1`). From no class to local: multicast, in either spelling, and the IPv4-mapped spelling of 100.64.0.0/10.
- `check_threat_intel`'s reply for a target it excludes names RFC 2606 and RFC 6761 (example domains), RFC 5737, RFC 3849 and RFC 9637 (documentation addresses), RFC 2544 and RFC 5180 (benchmarking addresses), ATIS-0300115 and Ofcom's drama numbers (fictional phone numbers) and RFC 1122 and RFC 4291 (unspecified addresses), and no longer RFC 6890, whose reserved space is now local. For a local address it replies that the target is a local address and that no threat intelligence service was asked, where it used to present Cloudflare Radar's static record as "Cloudflare Radar Intelligence for Domain" (#1174).
- Shodan InternetDB's and Cloudflare Radar's static records name what the target is: "Documentation or benchmarking address" with RFC 5737, 3849, 9637, 2544 and 5180, "Unspecified address" with RFC 1122 and 4291, "Private / local network space", "Fictional phone number", an example domain or a local domain. Radar used to give every address and phone number it did not ask about a domain summary (#1174).
- `docs/TESTING.md` holds the test vocabulary and conventions (#1308). By those conventions, tests double only edges, each through one seam and one shared fake with a contract suite, and no test starts a real gh; tests find the repository root and their test data through `tests.support.paths`; `tests/` is to mirror `src/devops_cli`; tests are named after behaviour in glossary terms and compare whole values; and no test asserts on elapsed wall-clock time. It also says which tests a narrowed `devops ci test` run selects. ADR 0007 records why tests double only process edges. Conventions whose mechanisms are still to come are marked as targets, and the file lists what exists today.
- AGENTS.md, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/SELF_IMPROVEMENT.md`, `.devops/review.md` and three knowledge base articles link `docs/TESTING.md` instead of stating their own test rules (#1308). AGENTS.md no longer requires linear asserts to be merged into tuple comparisons: Ruff's C901 does not count asserts.
- `devops test run --changed` maps a change through the selector `devops ci test` uses, in place of its own name table: a changed source module selects the test modules named for it, at any depth, and those that import it; a conftest of fixtures selects its own directory, and one that binds a pytest hook the whole suite. It never passes a deleted test module to pytest, and it names each changed source no test module covers.
- A change to a helper module under `tests/` selects the tests it reaches, read with `ast` once per run: the whole suite when it defines a fixture or binds a `pytest_*` name, when a conftest or such a helper imports it, or when it is deleted, renamed away or unreadable; otherwise the test modules that import it, directly or through other modules. `devops ci test` runs the whole suite, or refuses under `--no-fallback`, for a helper that reaches every test and for one deleted since the coverage index was built.
- The swallowed-failures ratchet runs as a module, `uv run python -m tests.test_swallowed_failures_ratchet --lower`, and its usage line names that command.
- A narrowed `devops ci test`, given paths and no `-n`, runs serially for up to 12 test modules (`DEFAULT_CI_TEST_SERIAL_MAX_FILES`) and on 4 workers above that (`DEFAULT_CI_TEST_NARROWED_WORKERS`), instead of starting 16 workers for a few covering tests (#1669). The commit hook's run for a one-module change took 10.6 s and 12 CPU-seconds, against 17.7 s and 183 CPU-seconds before. The full suite, the fallback to it and `devops ci` keep `-n logical`, and a given `-n` is kept.
- The targeted-test command is `uv run devops ci test tests/test_<feature>.py`, so a direct run gets the same worker sizing, in AGENTS.md, CONTRIBUTING.md, `docs/SDLC.md`, `docs/SELF_IMPROVEMENT.md`, `docs/ROUTINE_TASKS.md`, the knowledge base and the generated AGENTS.md block; `docs/TESTING.md` describes the per-test bound and the narrowed run's workers and stop. AGENTS.md and the generated AGENTS.md block say the fail-to-pass check fails any pull request whose replay pytest could not run on base, as when the overlaid `tests/` import support the base lacks or the pull request changes dependencies or the test harness, that such a pull request declares the not-applicable line, and that a changed test that only fails to collect on base is reported as errored.

### Removed
- `run_gh`'s own page loop, `run_gh_async`, `parse_paginated_json` and the `aiolimiter` dependency ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- Retired private `pydantic_ai._run_context`, `pydantic_ai._models_by_id`, and `pydantic_ai._ssrf` imports across `src/`, routing network safety checks through `devops_cli.core.validation`.
- Facade package re-exports across `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.mcp`, and `devops_cli.github`, which now contain single module docstrings; callers across `src/`, `tests/`, and knowledge base documentation import directly from defining submodules.
- Unused `StagePipeline` protocols, dead module `src/devops_cli/ai/agents/pydantic_agent.py`, `src/devops_cli/ai/pipeline_protocol.py`, and the legacy `src/devops_cli/pipeline/` package.
- Eager imports of heavy packages (`pydantic_ai`, `kubernetes`, `docker`, `fastmcp`, `qdrant_client`, `opentelemetry`) on `--version`, root `--help`, and all 39 command group `--help` dispatches, with startup import budgets enforcing cumulative import time under 0.5 s for `devops_cli.main` and under 1.0 s for any command help.
- `verify_test_paths_isolated`, its check and `CONST_ISOLATED_TEST_ENV_KEYS`: the check read only paths the suite's own fixtures set, so it could not fail.

### Fixed
- In review group analysis, a model reply cut at its token cap (`finish_reason="length"`) is rejected as `reply-truncated` without being parsed or shown, and recorded in analysis report rejections without retry.
- Names without a public suffix on the Public Suffix List (and names under `arpa` or `onion`) now count as local everywhere via `devops_cli.core.dns_names.is_public_dns_name`, replacing `CONST_LOCAL_DOMAIN_SUFFIXES` and hand-written `.endswith(...)` suffix checks across egress validation, AI spend pricing, Kubernetes URL auto-configuration, `web_fetch`, `PlaywrightBrowser.navigate`, and sandbox local whitelisting (#887).
- Public-only URL egress validation (`validate_url_egress` and `is_loopback_or_private_host`) now refuses non-public hostnames and names rejected by `dnspython` (IDNA 2008) before performing any DNS lookup (#887).
- `devops k8s configure-urls` now preserves any configured URL whose host is a domain name (including private zones under `lan`, `internal`, `local`, `cluster.local`, and single-label names) when discovery finds only an IP or loopback URL, and matches preferred Ingress domains on DNS label boundaries via `is_at_or_under` (#887).
- Domain list fields (`WebSearchTool`, `WebFetchTool`, `WebFetch`, `Researcher`, `PlaywrightBrowser`) and `k8s.domain` / `cloudflare.domain` now refuse root (`.`, `@`, `""`) and leading-dot entries at load time, while treating blank or whitespace-only `k8s.domain` and `cloudflare.domain` values as unset (`None`) (#887).
- Picked AI model reasoning parameters from declared capabilities rather than model name heuristics, querying gateway `/model/info` cached per process, supporting direct configuration for models outside the gateway, and eliminating transparent 400 error-text scraping.
- A 422 for an invalid SSH signing key, or one in use on another account, is no longer taken as registered: on the session and on gh, a 422 counts as registered only when the key listing holds the key or can't be read ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- A board owner gh project could not look up is asked for again as `@me` at once, and where no `@me` fallback exists it is a rate limit only when GraphQL's own budget is spent or can't be read ([#983](https://github.com/dan-petty/devops-cli/issues/983)).
- `devops ci test .python-version --no-fallback` refuses like the other files that force a full run; it passed with nothing run, because the leading dot was stripped with the `./`.
- A file that forces a full run, changed only since the coverage index was built, no longer forces one, or a refusal under `--no-fallback`, on every later `devops ci test` run: the index counts as stale, the given files are selected by name and import, and a warning names the file.
- `devops pr check-readiness` exempts a release-process pull request from grounding only by the files it changes (#1344). A cut pull request, `chore/cut-vX.Y.Z` into `release/vX.Y.Z`, is exempt when it only modifies the cut's files (`pyproject.toml`, `src/devops_cli/__init__.py`, `uv.lock`, `CHANGELOG.md`, `docs/ROADMAP.md`) and removes `changelog.d/<issue>.md` fragments, as the cut commit does; before this change it was held to grounding and failed with "closes no issue". A merge of `main`, `chore/open-vX.Y.Z-main` into `release/vX.Y.Z`, is exempt when it changes only the cut's files and what `main` changed since its merge base with the release branch, read with one compare request; before this change any `chore/open-vX.Y.Z[-slug]` pull request was exempt whatever it changed, so code fixes reached `release/v0.2.28` with no issue, task file or changelog fragment. A release-process pull request that changes any other file, both paths of a rename included, is held to grounding with one blocker naming those files, and one whose file list or compare can't be read, or whose compare lists GitHub's limit of 300 files, is held with a blocker naming the failure.
- `devops pr monitor` took any review whose author's login contained "copilot" for Copilot's. A review is now Copilot's only by Copilot's exact login on review records, and a timeline `reviewed` event ends Copilot's pass only by the id of one of its reviews, since the timeline names the same account `Copilot` (#1345).
- Chat requests one process sends through the LLM gateway now stay within the gateway's backend slot count (3), however many `ai.ollama_urls` are configured (#1354). The limit is per process: a second CLI process, or the in-cluster Service, takes slots of its own. Gateway reviews sized their file workers by the Ollama URLs, which add no gateway capacity, and every file ran its personas in parallel, so a review with three URLs could keep more than 3 requests in flight and rebuild the backend queue #1069 meant to prevent. With the `gateway` provider, the persona stage now reviews at most 3 files at once, and an explicit `devops review --concurrency` above 3 is lowered to 3 with a warning that names both numbers. `devops review benchmark` records the concurrency its reviews ran at, so a gateway benchmark asked for 8 records 3. Every chat request the process sends to the gateway, streamed or not and from any command, now waits for one of the 3 slots, and a stream keeps its slot until it closes. A request that waits more than 900 seconds fails with an error naming the slot count. Model listing, gateway health probes and embeddings take no slot. Other providers are unchanged, including an `ollama` client with `ai.gateway_enabled` set, whose chat requests go to Ollama.
- A structured LLM reply no longer rebuilds its response model's schema. Each reply built a `FormattedLLMResponse[T]` class that pydantic caches only weakly, so after a garbage collection the next reply spent about 30 ms of CPU rebuilding it (#1354).
- Removed the synthetic `"devops-cli"` identity fallback in `_get_session_login` (`src/devops_cli/roadmap/run.py`), allowing GitHub login lookup failures to raise typed `GitHubOperationError` exceptions directly and fail closed (#1409).
- Ensured job clone setup and change filtering fail closed when the session login lookup fails, preventing git identity configuration with `"devops-cli"` and avoiding self-triggering loop failures against unauthenticated sessions.
- Switched `GitHubSession.login` to use the session REST transport (`GET /user`) rather than shelling out to the `gh` CLI subprocess edge, tested against `GitHubApiFake`.
- Mapped only `httpx2.TransportError` and transport subclasses to AI provider connection errors in `LLMClient._retry_chat_dispatch`, preventing non-transport errors from falsely reporting "Cannot connect" and preserving actual exception names (#1609).
- Hardened `LLMResponseCache` disk cache eviction against unhandled `OSError` and `FileNotFoundError` when files are concurrently deleted across worker processes.
- Resolved intermittent review stall test flake in `test_five_personas_with_one_transient_503_sees_exactly_six_calls` by isolating response cache and settings cache state across worker runs.
- A pull request that delivers part of an item planned as several says `Part of #<issue>` instead of a closing keyword, and `devops pr check-readiness` grounds it on that issue: the issue is open and an item of the base's release, and the pull request changes its task file, which may read `**Status**: In Progress`. A body that names both a closing keyword and a part reference, or two part references, is one blocker that says so. `devops roadmap close` acts only on closing keywords, so the item's last pull request closes it, and that pull request adds the item's changelog fragment. `devops roadmap reprioritize` counts a part pull request's updates as the item's activity, so an item busy with its parts is not stalled and moved on part-way through, and a part pull request keeps its item from a trim, as a closing one does. A pull request body's closing keywords and part references are read only in its prose: a tilde or unclosed fence, indented code and an HTML comment no longer close an issue or name a part ([#1617](https://github.com/dan-petty/devops-cli/issues/1617)).
- Tempo runs in the `otel` namespace, whose PodSecurity `restricted` admission refused every pod since trace storage shipped in v0.2.35: `k8s/otel/tempo-values.yaml` sets the `RuntimeDefault` seccomp profile on the pod and a container that drops every capability, cannot escalate and keeps a read-only root filesystem ([#1627](https://github.com/dan-petty/devops-cli/issues/1627)).
- Tests wait for something another thread does with one generous bound, `THREAD_HANDOFF_BOUND_SECONDS` (30 s) in `tests/support/waits.py`, instead of 1- and 2-second deadlines that failed correct code while a loaded host kept a ready thread waiting for a CPU. A wait still returns as soon as its event fires, so a passing test is no slower (#1664).
- Anything a test holds alive or blocked, a sleeping process group member or a job held until the test lets it go, outlives the wait that observes it or records that the test released it, so a hold that ran out on its own can no longer pass a test with its bug back in.
- `test_once_the_model_answers_lookups_stop_taking_turns` holds only the workers' embedding requests at its barrier: the tracer's exporter threads posted trace exports through the same patched `httpx2.Client.post`, took a worker's place at the barrier and broke it.
- Two Service pause tests no longer depend on which worker starts first: a budget refusal holds every round that has not started, so the refusals now wait until the rounds the tests need have started.
- A wait that checks that nothing happens keeps its short window, opened only once the competing thread is at the point where the event would happen, and says so in a comment.
- Test processes start no idle OpenBLAS threads: `tests/conftest.py` sets `OPENBLAS_NUM_THREADS=1` before its own imports, so a 16-worker run holds 2 threads per worker at collection (briefly 3 while OpenTelemetry's resource detection runs) instead of 17 against the container's pids.max. `devops ci test --repeat` loads pytest-randomly, which imports numpy before the conftest runs, so that one process keeps OpenBLAS's per-CPU threads.
- The embeddings tests no longer look up the Qdrant host (refused by the suite's guard) and sleep through about 3 s of retries: their fixture answers the collection check too.
- A test that hangs fails at a per-test timeout instead of holding `devops ci`, and every xdist worker it owns, until a person kills it: pytest-timeout 2.4.0 joins the dev group, and `[tool.pytest.ini_options]` sets `timeout = 600` with `timeout_method = "signal"`, so the stuck test fails in its own process with pytest-timeout's report naming it, and the run and its worker carry on (#1669). 600 s is a hang bound: the slowest test in 185 cached gate runs took 139 s under heavy load, and the bound stays under half the run's 1800 s timeout, so a hung test is reported by name before the whole run is stopped. A test that needs longer says so with `@pytest.mark.timeout(<seconds>)`.
- `devops ci test` stops the whole process group of the pytest it starts, `uv`, pytest and its workers, when the run outlives its timeout, and fails naming the command and the timeout. It used to run pytest through `subprocess.run`, whose timeout killed only `uv` and left pytest running. Ctrl-C, SIGTERM and SIGHUP stop the run the same way: the group gets the SIGINT a terminal would have sent, so pytest runs its teardown, then SIGTERM, then SIGKILL, which a second signal brings forward but cannot skip. A run started off the main thread, as from the MCP server, sets no signal handlers, and an ignored SIGHUP stays ignored, so `nohup` still works.
- `devops ci fail-to-pass` reports a replay whose pytest could not run on base as one that could not run, and fails the check for any pull request, feature or defect: pytest was interrupted (exit 2), stopped with an internal error (3) or a usage error (4), or wrote no complete JUnit report, as when the overlaid `tests/` import support the base lacks. A report that is empty or cut short counts as none. The report names pytest's exit status, the replayed test files and the last lines of pytest's output, up to 256 characters, printed as pytest wrote them. Such a replay used to read as "0 failed on base (0 failed and 0 passed in …; 0 errored)", so a feature passed the check with nothing replayed and a defect failed it for the wrong reason, that no changed test failed. A pull request whose replay cannot run on its base still passes with a `Fail-to-pass: not applicable: <reason>` line, pytest's exit 5, no tests collected, is still an empty replay, and a changed test that only fails to collect on base is still reported as errored.
- `devops roadmap intake` never folds a candidate into a completed/Done item; candidates matching a closed completed item are placed and filed as a new issue referencing the original in their body (#1671).
- Added `ignoreDifferences` entry with `jqPathExpressions` for Argo CD `Application` resources in `k8s/argocd/bootstrap/cluster.yaml` to ignore dynamically injected PreDelete and PostDelete finalizers (such as `k8s-monitoring`'s clean-up hook), preventing the cluster app-of-apps from repeatedly stripping and re-adding them on every sync cycle (#1674).
- `devops k8s deploy-stack --stack all` deploys every manifest and chart deployed by Argo CD Applications: added the pinned Traefik Helm chart (`kube-system/traefik`), GPU feature discovery DaemonSet (`Path("gpu-feature-discovery")`), the wildcard Cloudflare Ingress routes (`k8s/ingress/ingress-routes.yaml`), Portkey (`k8s/llm/portkey/*`), and the Valkey run index (`k8s/llm/valkey-runs.yaml`) ([#1675](https://github.com/dan-petty/devops-cli/issues/1675)).
- Helm conflict adoption (`_adopt_helm_resource_if_conflict`) refuses to adopt conflicting resources for the Traefik release and warns that stock k3s must be run with `--disable traefik` ([#1675](https://github.com/dan-petty/devops-cli/issues/1675)).
- Dropped NetworkPolicy undeployed exemptions (`UNDEPLOYED_NETWORK_POLICIES`) in `tests/test_k8s_network_policies.py` and replaced the hand-injected Traefik mapping in `tests/test_k8s_argocd_apps.py` with an exhaustive bidirectional counterpart mapping ([#1675](https://github.com/dan-petty/devops-cli/issues/1675)).
- `devops roadmap intake` asks the model again when its proposal names a value off its list (type, Priority, Value, or Effort), providing structured feedback in `problem`. A second off-list reply reports both problems in the run report. A candidate filed via `--title` that still cannot be placed exits non-zero under `--confirm` (#1677).
- Intake never closes as duplicate an item a person planned (a milestone a person placed, or a Priority a person set on its card or label) or an item older than its matched original, reporting it instead as a possible duplicate held for a person (#1686).
- Made CLI startup import budget tests structural and deterministic based on unique and `devops_cli` module counts rather than wall-clock seconds, preventing CI gate failures caused by host scheduling jitter on busy multi-core systems (#1687).
- Removed cross-process startup test lock file (`.data/importtime.lock`) and obsolete wall-clock seconds constants, enabling concurrent test execution under `pytest -n` without serialization contention.
- The `devops ci maintain` test no longer runs a real `uv audit` against the live advisory database, so a newly published advisory can no longer fail the test suite (#1697).
- The fail-to-pass check runs only on pull requests into a release branch, where each item proves its fix. It no longer runs on the release pull request into main, which carries items that each passed and whose tests cannot replay on main's tree once a release changes the test harness; since a replay that cannot run fails the check (#1669), it failed the v0.2.37 release pull request (#1721).
- The CI Quality Gate's Changed-Test Independence job runs only on pull requests into a release branch. On the release pull request into main every test the release touched counts as changed, and each item already passed the job against the release branch; the v0.2.37 release pull request spent more than 20 minutes in it (#1723).

### Security
- **Every address is in exactly one class, and only public addresses reach a threat-intel service (#1174).** `security/reference_extractor.py` classifies addresses with Python's `ipaddress` instead of hand-kept RFC tables. An address is a documented example if it is in documentation or benchmarking space (`CONST_DOCUMENTATION_IP_NETWORKS`: RFC 5737, RFC 3849, RFC 9637, RFC 2544, RFC 5180); public if it is global, not reserved and not multicast, outside 192.88.99.0/24 and the deprecated site-local fec0::/10, which Python still reads as global although IANA does not (`CONST_NON_GLOBAL_NETWORKS_STDLIB_READS_GLOBAL`); and local otherwise. An IPv4-mapped IPv6 address such as `::ffff:192.0.2.1` is in the class of the IPv4 address it carries. Multicast addresses such as `224.0.0.1` and `ff02::1` were in no class, so `check_threat_intel` and `CloudflareRadarClient.check_domain` sent them to Cloudflare Radar's domain lookup; they are now local, and no request is made. Radar answers an unspecified address (`0.0.0.0`, `::`, `http://0.0.0.0:8000`) from its static example record, as `check_threat_intel` rejects it; `::` used to reach the domain lookup. `is_example_or_reserved_ip` is removed; `is_example_ip` replaces it.
- **A target is classified by the address it names, whatever its spelling (#1174).** Every address class, `is_example_or_invalid_network_target`, Shodan InternetDB, Cloudflare Radar and `check_threat_intel` read a target as `network_target_address` reads it: without the punctuation prose leaves after it, as the host of a URL or `host:port`, and in the legacy numeric spellings a resolver dials (`2130706433`, `127.1`, `0x7f.0.0.1` are 127.0.0.1), with no lookup. `100.64.0.1.`, `224.0.0.1,`, `10.0.0.1.`, `2130706433` and `http://100.64.0.1./v1` used to reach Radar's domain lookup, from `check_threat_intel`, `CloudflareRadarClient.check_domain` and its batch path; no request is made for them now. A public address with a trailing mark, such as `8.8.8.8.`, used to go to Radar too, and is now sent to Shodan as `8.8.8.8`.
- **The sandbox local whitelist refuses `host.docker.internal` and never emits an empty egress rule (#1174).** `host.docker.internal`, in any case and with or without a trailing dot, is refused when `SandboxNetworkConfig` is validated, before any lookup, with a message asking for the IP address or CIDR the cluster reaches the host on. It used to become a `127.0.0.1/32` ipBlock: the pod's own loopback, not the host gateway. A loopback entry (`localhost`, `127.0.0.1`, `[::1]:8080`, `127.0.0.0/8`) now adds no egress rule instead of a no-op ipBlock, since NetworkPolicy never polices a pod's loopback. An entry that resolves to no address adds no rule, since a rule with an empty `to` would allow every destination on its port.
- Deployed the `argocd-default-perimeter` NetworkPolicy through Argo CD by adding `k8s/argocd` as a source in `k8s/argocd/apps/argocd.yaml`, establishing default-deny ingress and egress isolation for the `argocd` namespace (#1673).
- Disabled the unused ApplicationSet controller by setting `applicationSet.replicas: 0` in `k8s/argocd/values.yaml`, preventing container creation and eliminating unneeded cluster-admin execution while preserving RBAC definitions.
- aiohttp moves from 3.14.3 to 3.14.5, which fixes GHSA-494j-54xm-rwp3, GHSA-5wr8-gcqf-gqf3 and GHSA-2g87-pp6c-29x5; yarl moves to 1.25.1, which aiohttp 3.14.5 requires. `uv audit`, and with it the audit check of `devops ci`, passes again (#1697).

## [0.2.36] - 2026-10-17

### Added
- **Authenticated Qdrant Prometheus Scrape & Restored Dashboard Row (#823)**: Enabled `metrics.serviceMonitor` in `k8s/llm/values-qdrant.yaml` with `Bearer` token authorization from Secret `qdrant-api-key` (`key: api-key`) so Alloy (`k8s-monitoring`) scrapes Qdrant's protected `/metrics` endpoint on port 6333. Added the `docker.io/qdrant/qdrant:v1.19.1` metric family capture (`tests/fixtures/metrics/qdrant.yaml`), restored the Qdrant row (`Qdrant Request Rate and Errors`, `Qdrant Request Latency p95`, and `Qdrant Collections and Vectors`) in `k8s/monitoring/dashboards/llm-stack.json` without constant fallbacks, and enforced Qdrant `ServiceMonitor` and PromQL series/label verification in `tests/test_stack_dashboards.py`.
- Add `devops ci fail-to-pass` and `.github/workflows/fail-to-pass.yml` to replay a pull request's added or modified `tests/**/test_*.py` files against its merge-base tree with the head's `tests/` overlaid, gating defect PRs on at least one call-phase failure on base unless `Fail-to-pass: not applicable: <reason>` is declared (#844).
- Enforced per-kind suppression comment and configuration waiver ceilings across `src/`, `tests/`, and `pyproject.toml` via `tokenize.COMMENT` inspection (`type: ignore`, per-rule `noqa`, `nosec`, `pragma: no cover`, `pragma: no mutate`, file-level directives, `ast-grep-ignore`, Ruff `per-file-ignores`, `[[tool.mypy.overrides]]`, and coverage `omit`), and lowered `DEFAULT_C901_SUPPRESSION_CEILING` from 65 to 51 (#849).
- Route all LLM JSON repair entry points (`repair_json_string`, `extract_json_block`, and `chat_structured`'s `_parse_json_payload`) through a single `repair_json(text, *, source)` seam in `devops_cli.ai.response_repair` that emits `devops_cli_ai_json_repairs_total` labeled by `source` and preserves top-level lists in unclosed markdown fences (#875).
- Run review static analysis tools (`ruff`, `mypy`, `pluto`) at the target repository's declared Python and Kubernetes versions (reporting `coverage_gap` when undeclared) and gate tool findings and coverage on a 5-tuple cached canary check against recorded `(rule_id, line)` expectations (#1143).
- Added the tested Semgrep review rule pack (`src/devops_cli/review/rules/k8s-networkpolicy-ingress-any.yaml` and `.test.yaml`), `rules.lock` manifest verification (`devops review rules test [--check]`), expected `tool`/`rule` annotations on `tests/fixtures/review_recall/recall_set.json`, and the path-filtered `Rule Pack Tests` job in `.github/workflows/ci.yml` ([#1145](https://github.com/dan-petty/devops-cli/issues/1145)).
- Add bounded per-group model analysis for admitted review findings (`devops_cli.review.analysis`), grouping findings by enclosing symbol or rule, Kubernetes `(namespace, kind, name)`, or package `purl`, grounding each group's single model call in installed-version rule documentation and secret-masked code excerpts, verifying every doc quote, code quote, member finding citation, Python code block syntax, version string, and `.devops/review.toml` suppression note via deterministic G10 checks, writing `analysis.json` and a separate `## Model Analysis (Model-Written)` section in `review.md` while keeping `findings.json` and `findings.sarif` untouched, and gating `reference_coverage` in `devops review score` and `devops ai runs check --max-reference-coverage-drop` ([#1147](https://github.com/dan-petty/devops-cli/issues/1147)).
- Enable Argo CD's web terminal (`configs.cm."exec.enabled"` in `k8s/argocd/values.yaml`), so `role:admin` opens a shell in any pod an Application manages from the pod's Terminal tab; the chart grants `argocd-server` `create` on `pods/exec` ([#1585](https://github.com/dan-petty/devops-cli/issues/1585)).
- Reach the Kubernetes API off the home network at `k8s.<domain>` through the Cloudflare Tunnel: `k8s/cloudflared/networkpolicy.yaml` lets cloudflared reach the API server on 6443, `cloudflared` is a `tools.lock` binary that `devops install-tools --tool cloudflared` installs, and `k8s/README.md` gives the TCP route, the `cloudflared access tcp` listener and the kubeconfig context ([#1595](https://github.com/dan-petty/devops-cli/issues/1595)).
- zizmor is a registered scanner: `devops scan report` and its SARIF, which CI uploads to code scanning, carry its workflow findings under zizmor's own audit names as rule IDs, and reviews run it on a repository's GitHub Actions workflows and action files. Its findings are published and do not gate, so `devops scan workflows` stays the gate on template injection, unpinned actions and excessive permissions; an isolated review scan hands it a configuration with no rules changed ([#1608](https://github.com/dan-petty/devops-cli/issues/1608)).

### Changed
- Replaced the 4-subsystem Tarjan circular-import test with whole-tree AST import-cycle (`graphlib.TopologicalSorter`) and interface-layer (`devops_cli.commands` boundary) invariants in `src/devops_cli/core/import_graph.py`, running on the single `_parse_src()` pass in `test_the_source_tree_keeps_its_structural_invariants`, and moved `load_local_contracts` into `devops_cli.ai.rag.library_store` and release-cut domain helpers into `devops_cli.release.cut` (#848).
- `devops scan workflows` titles each finding `[<audit>] <description>`, without the `ZIZMOR:` prefix, so its rule ID in SARIF is the audit's name ([#1608](https://github.com/dan-petty/devops-cli/issues/1608)).
- `.github/zizmor.yml` disables zizmor's self-repository audit, which asks for `$/<path>` action references that actionlint 1.7.12 rejects, until the pinned actionlint accepts them ([#1615](https://github.com/dan-petty/devops-cli/pull/1615)).

### Fixed
- **OpenTelemetry Delta Metric Aggregation, Exponential Histograms & Prometheus Client Exposition** ([#792](https://github.com/dan-petty/devops-cli/issues/792)): Replaced per-point OTLP metric JSON construction and concurrent worker-pool HTTP dispatch in `OTelTelemetryClient` with an OpenTelemetry SDK `MeterProvider` (`InMemoryMetricReader` with `DELTA` temporality and `ExponentialBucketHistogramAggregation`) that aggregates all counter, histogram, and gauge recordings within a process and flushes one batch at command end or `shutdown()`, eliminating intra-process out-of-order delta drops at `deltatocumulative`. Enabled `--enable-feature=native-histograms` in `k8s/monitoring/prometheus-values.yaml`, added mean (`_sum / _count`) and sample-count targets to duration panels in `k8s/monitoring/dashboards/devops-cli.json`, quieted `httpx`, `httpx2`, and `httpcore` loggers to `WARNING` in Service mode, and replaced hand-rolled Prometheus exposition formatters and regex parsers across `telemetry/metrics.py`, `ai/spend/prometheus.py`, `server/routes/telemetry.py`, `server/service.py`, and `sandbox/metrics.py` with `prometheus-client==0.26.0`.
- Fail closed in `devops pr check-readiness` when review discussion threads cannot be retrieved, reporting the error as a readiness blocker instead of assuming zero unresolved threads, and add regression tests for `devops ai runs check` on empty comparisons and ambiguous run-ID prefixes ([#797](https://github.com/dan-petty/devops-cli/issues/797)).
- Make `devops docs generate` and `devops docs check` fail closed when a command module, FastMCP tool listing, or exception module fails to import, and render group-callback options, MCP array item types and enum values, all project config file candidates and `Settings` sections in `docs/CONFIGURATION.md`, and all `DevOpsCLIError` subclasses with their constructor error and exit codes in `docs/ERRORS.md` (#854).
- Emit failing `pytest.fail(...)` unit test scaffolds instead of presence-only `hasattr` assertions in `devops ai test-gen` and `ai_test_gen`, and update CLI and MCP wording to report scaffolds rather than synthesized unit tests ([#856](https://github.com/dan-petty/devops-cli/issues/856)).
- `devops ci maintain` audits with `uv audit`, the command the `audit` check runs, instead of the undeclared `pip-audit`, and reports an audit that could not run apart from one that found vulnerabilities ([#861](https://github.com/dan-petty/devops-cli/issues/861)).
- `devops ci fail-to-pass` replays with `--continue-on-collection-errors`, so a fix that adds a module and a test file importing it, which cannot be collected on base, still has its other changed tests counted; pytest had stopped at the collection error and run none of them ([#861](https://github.com/dan-petty/devops-cli/issues/861)).
- `docs/SDLC.md` no longer claims weekly Dependabot audits, `pip-audit` or SLSA Level 3, and names the supply-chain controls the repository runs ([#861](https://github.com/dan-petty/devops-cli/issues/861)).
- Skip creating review session directories or persisting `findings.json`, `candidates.json`, `findings.sarif`, `review.md`, and per-file JSON payloads during dry-run reviews (#872).
- Apply each `devops roadmap intake` candidate's writes on its own: a candidate whose GitHub write fails is skipped with a warning naming it and the error, the round's other candidates are still placed, and the round then fails with `RoadmapIntakeError` (`ROADMAP_INTAKE_FAILED`) naming every skipped candidate and its error's class, so `devops roadmap intake --confirm` exits 1 and `devops roadmap run` reports the intake job failed. A rate limit or GraphQL budget refusal still stops the round at once, and the next round decides a skipped candidate again after the fresh ones ([#1443](https://github.com/dan-petty/devops-cli/issues/1443)).
- Print step, raw and leveled messages (`print_info`, `print_error`, `print_warning`, `print_success`, `print_muted`, `print_step`) as one line for the terminal to wrap, so Rich no longer writes a newline inside a command a message names, and end an abandoned `devops devcontainer unlock-keyring` prompt's line before the message that follows it ([#1588](https://github.com/dan-petty/devops-cli/issues/1588)).
- `devops cloudflare tunnel sync` places a new hostname before the first wildcard rule that would match it, since cloudflared takes the first matching rule; it appended new hostnames after every rule, so a host under an existing `*.<domain>` route was never reached ([#1595](https://github.com/dan-petty/devops-cli/issues/1595)).
- A `tools.lock` build may name its own `format`, for a tool packed differently per platform such as cloudflared's macOS `.tgz` ([#1595](https://github.com/dan-petty/devops-cli/issues/1595)).
- Tests no longer leak keyring backends: keyring registers every `KeyringBackend` subclass a test defines as a candidate for the rest of the process and picks the highest-priority one when it next detects a backend, so a fake from `tests/test_config_cmd.py` became a later test's keyring and failed its secret writes or reads. An autouse fixture unregisters the backend classes each test defines and restores keyring's chosen backend ([#1601](https://github.com/dan-petty/devops-cli/issues/1601)).
- `devops pr monitor` and the other readers of a pull request's checks through the REST check-runs API drop a cancelled run that a later-started run of the same check replaced, as a workflow that cancels its in-progress run on a newer event leaves; a cancelled run with no newer run, and every failure, still fail the pull request ([#1602](https://github.com/dan-petty/devops-cli/issues/1602)).
- `reset_tracer()` shuts the tracer it drops down first, waiting for its exports in flight: every test resets the tracer, and a test's queued OTLP exports ran on into the next test, whose dry-run socket probe saw connections to `localhost:4318` it never made ([#1604](https://github.com/dan-petty/devops-cli/issues/1604)).

### Security
- Declared MCP `ToolAnnotations` (`readOnlyHint`) on all 155 FastMCP tools in `src/devops_cli/ai/mcp/server.py`, changed `tf_apply` to default to `auto_approve=False`, enforced the annotation contract and argument-mutating floor in `tests/test_fastmcp_contracts.py`, and carried `readOnlyHint` into `MCPToolInfo`, `devops mcp export-schemas`, and `docs/MCP_TOOLS.md` ([#857](https://github.com/dan-petty/devops-cli/issues/857)).
- Audit GitHub Actions workflows with zizmor 1.30.1, pinned in the dev group: `devops scan workflows` runs it offline, shows every finding and fails on template injection, unpinned actions and excessive permissions, and `devops ci` runs it as the `zizmor` check. The five `run:` blocks that interpolated `${{ }}` expressions, including the release workflow's dispatched `version` input, take their values through `env:` ([#861](https://github.com/dan-petty/devops-cli/issues/861)).
- The service image takes current Debian security updates: its final stage, which runs `apt-get upgrade`, is named `service` and never reused from the build cache (`no-cache-filters: service`), so a cached layer no longer kept `libcurl3t64-gnutls` 8.14.1-2+deb13u5 after deb13u7 fixed CVE-2026-8286, CVE-2026-8927 and CVE-2026-92392 ([#1615](https://github.com/dan-petty/devops-cli/pull/1615)).
- Every `actions/checkout` states `persist-credentials`, and only the release job, which pushes its tag, keeps the token in `.git/config` (zizmor's artipacked); a test holds every workflow to it ([#1615](https://github.com/dan-petty/devops-cli/pull/1615)).

## [0.2.35] - 2026-10-13

### Added
- **Active marginalia & epistemic scratchpad (`devops ai research annotate`)**:
  - Added file-anchored observation and hypothesis tracking under `.data/marginalia/<file_hash>.jsonl`.
  - Supported five typed marginalia classifications: `ASSUMPTION`, `HYPOTHESIS`, `CONTRADICTION`, `QUESTION`, and `TODO`.
  - Added `devops ai research annotate` command for recording and viewing marginalia with JSON and YAML formatting support.
  - Automatically injected prior marginalia into `devops ai research forage` trails and node context.
- **Socratic inquiry & knowledge gap formulator (`devops ai research socratic`)**:
  - Added metacognitive knowledge gap and ambiguity analysis for task self-assessment.
  - Implemented structured output models for `GAP`, `AMBIGUITY`, and `UNDERSPECIFIED_CONTRACT` with associated rationales.
  - Added minimal diagnostic probes emitting concise clarifying questions and concrete code lookup instructions bounded by `--max-probes`.
  - Added `devops ai research socratic` subcommand supporting table, JSON, YAML, and Markdown formats.
- **Cross-domain analogical pattern retriever (`devops ai research analogies`)**:
  - Added multi-vector topological clustering over the Knowledge Base RAG collection to discover cross-domain structural pattern isomorphisms.
  - Implemented `CrossDomainAnalogy` and `AnalogyReport` structured output models surfacing source module, target module, shared structural pattern, confidence score, and invariant mechanisms.
  - Added `devops ai research analogies` CLI subcommand supporting query filtering, source/target domain constraints, and table, JSON, YAML, and Markdown output formats.
- **Living mental model synthesizer & causal graph distiller (`devops ai research model`)**:
  - Added progressive synthesis of sprawling research observations into structured YAML mental models under `.data/research/mental_model_<topic>.yaml`.
  - Implemented finite-state machine transitions (`StateTransition`), causal directed acyclic graphs (`CausalGraph`, `CausalNode`, `CausalEdge`), and verifiable invariant rules (`InvariantRule`).
  - Added `devops ai research model` command supporting progressive revision updates, `--observations`, `--file`, `--show`, and YAML, JSON, Markdown, and table formatting.
- **Kubernetes orphaned volume reclamation (`devops k8s volume reclaim`)**:
  - Added `devops k8s volume reclaim <name>` to safely reclaim persistent volumes stuck in `Released` or `Failed` phase.
  - Implemented pre-mutation verification confirming volumes are genuinely orphaned: phase check (`Released` or `Failed`), claim absence check, and pod mount check across all namespaces.
  - Added confirmation gating requiring `--yes` in non-interactive sessions, and request-free `--dry-run` simulation displaying exact API operations.
- Standardized output format adoption (`--format`, `-f` supporting `table`, `json`, `yaml`, `csv`) across all 144 CLI value commands via `emit_serialized` and `resolve_format` (#411).
- Structured property-based fuzzing test suites for boundary resilience across SARIF 2.1.0 parsing, `git worktree list --porcelain`, `git status --porcelain=v1` cache parsing, Argo CD drift analysis, and review JSON schema normalization (#416).
- **OCI container image packaging & standardized metadata validation (`devops devcontainer validate`)**:
  - Added `--oci-labels` and `--expected-source` options to `devops devcontainer validate` to structurally audit OCI annotations prior to container publication.
  - Implemented multi-platform Buildx compilation (`linux/amd64`, `linux/arm64`) with QEMU in container release workflows.
  - Added SLSA provenance attestations and SBOM generation to devcontainer and service image packaging pipelines.
- `devops ai gateway render`: render and apply LLM gateway configuration derived from Ollama profiles and service aliases, aligning `max_input_tokens` with tier context lengths, removing deprecated `weight` fields under `least-busy` routing, and outputting unified diffs (#478).
- `devops roadmap reprioritize`: record a durable tally of joins, descopes and trims on each item's job record, record release start size history, report release growth across releases, emit telemetry gauges, and visualize in Grafana (#1126).
- Deploy single-binary Grafana Tempo (`grafana-community/tempo` `3.1.0`) in the `otel` namespace backed by a `10Gi` `local-path` PersistentVolumeClaim (`Prune=false,Delete=false`) with `168h` (7-day) trace retention, Argo CD Application `k8s/argocd/apps/tempo.yaml`, Alloy `integrations.tempo` metrics scraping, and Grafana `Tempo` datasource (`uid: tempo`) linked to `loki` (`tracesToLogsV2`, `lokiSearch`) and `pyroscope` (`tracesToProfiles`) ([#1135](https://github.com/dan-petty/devops-cli/issues/1135)).
- Add `TempoConfig` (`settings.tempo`), `devops k8s tempo`, MCP tool `k8s_tempo_info`, built-in AI tool `k8s_tempo_status`, and Tempo OTLP v2 trace normalization (`normalize_tempo_spans`, `query_tempo_trace`) for `devops telemetry profile` and `devops sandbox traces` ([#1135](https://github.com/dan-petty/devops-cli/issues/1135)).

### Changed
- **Container manifests & release workflows**:
  - Standardized OCI Image Spec labels across `Dockerfile`, `.devcontainer/Dockerfile`, and `.github/workflows/release.yml`.
  - Pinned `uv` to `0.12.23` across devcontainer and production Dockerfile builds.
- Route OpenTelemetry Collector trace exports to `otlp_grpc/tempo` (`tempo.otel.svc.cluster.local:4317`) and update `k8s/monitoring/dashboards/otel-collector.json` to query `exporter="otlp_grpc/tempo"` and the `tempo` Grafana datasource ([#1135](https://github.com/dan-petty/devops-cli/issues/1135)).

### Removed
- Remove the ephemeral `jaeger` Deployment and Service (`k8s/otel/jaeger.yaml`), `settings.jaeger`, `devops k8s jaeger`, `k8s_jaeger_info`, and `k8s_jaeger_status`; on clusters not managed by Argo CD, remove the old resources with `kubectl delete deploy,svc -n otel jaeger` ([#1135](https://github.com/dan-petty/devops-cli/issues/1135)).

### Fixed
- **Repository-relative static scanner finding paths**:
  - Relativized Semgrep and Bandit static scanner findings against the scan root and review tree, eliminating absolute path leaks in candidate locations and descriptions.
  - Normalized candidate findings during the review pipeline's static-scan and admission stages so findings in `findings.json` and `review.md` consistently display canonical repository-relative paths (`app/x.py:12`).
- **PR review post without reporting (`devops review pr --post --no-reporting`)**:
  - Ensured PR review comments and findings telemetry metrics are built from verified findings even when the consolidated reporting stage is skipped via `--no-reporting`.
  - Preserved specific persona labels on review findings across metrics reporting in `FINDINGS_TOTAL` rather than falling back all findings to the default persona.
- `devops roadmap reprioritize`: the release-start trim and the cap descope pass over an item that a staying item depends on, re-evaluating dependencies after each trim, so a release never keeps an item whose open dependency it moved (#1123).

## [0.2.34] - 2026-10-11

### Added
- **Agentic information foraging & scent trails (`devops ai research forage`)**:
  - Implemented Pirolli & Card's Information Foraging Theory with a deterministic, local-only crawler exploring codebases via relational semantic scent.
  - Added multi-edge extractors across Python AST symbol imports (`ast`), internal Markdown references (`markdown-it-py`), and git co-change history (`GitPython`).
  - Added best-first heuristic search with `heapq` and cycle-detection ledger, scoring edges via BM25 lexical similarity (`ai/lexical.py`) and backtracking when information scent drops below threshold.
  - Registered `devops ai research forage` CLI command with interactive summary panels, detailed trail tables, and structured `--json` output.
- **Defect PR hardening audit and post-merge intake automation**:
  - Implemented `devops pr hardening-report [--pr N] [--fail-on-missing]` to audit merged defect pull requests for guardrail additions to declared hardening surfaces (`AGENTS.md`, `src/devops_cli/ai/tasks/*.md`, `src/devops_cli/ai/knowledge_base/`, `common_hallucinations.json`), explicitly excluding `docs/ROADMAP.md`.
  - Added reusable defect PR classifier (`classify_defect_pr`, `is_defect_pr`) in `src/devops_cli/github/defect_classifier.py` identifying defect pull requests by `type/bug`, `type/security` labels or Conventional Commits `fix(...)` / `fix:` titles.
  - Added post-merge audit workflow `.github/workflows/defect-pr-hardening-audit.yml` triggering on closed merged defect PRs, running the hardening audit with `--fail-on-missing`, and automatically handing findings to roadmap intake on failure with skip-not-fail for fork PRs.
  - Added workflow contract tests in `tests/test_workflow_contracts.py` validating triggers, permissions, step commands, intake routing, and static Typer command resolution.
- **Worktree inventory & safe orphan reclamation (`devops repos worktrees`)**:
  - Added `devops repos worktrees status` command to list every git worktree in the repository with per-entry commits ahead of main, dirty-path count, whether any other local or remote ref contains the tip, and git's `locked` and `prunable` status.
  - Added `--json` output option emitting typed arrays containing `ahead` (int), `dirty` (int), `contained` (bool), `locked` (bool), and `prunable` (bool).
  - Added `devops repos worktrees prune` with safe dry-run preview by default; without `--force`, removes only clean and contained worktrees and refuses unmerged, dirty, or locked checkouts.
  - Added `--force` support to remove worktrees regardless of clean or unmerged status, cleaning up metadata with `git worktree prune`.
  - Implemented NUL-separated porcelain parsing via `git worktree list --porcelain -z` per the #1440 convention to safely support worktree paths with newlines.
- **AGENTS.md Context Budget Enforced (`src/devops_cli/config/constants.py`)**:
  - Declared `CONST_AGENTS_MD_MAX_CHARS: Final[int] = 40_000` defining the maximum character budget for `AGENTS.md`.
  - Added unit test in `tests/test_agents_md_claims.py` verifying that `AGENTS.md` length is within `CONST_AGENTS_MD_MAX_CHARS` and `CONST_AGENTS_MD_MAX_CHARS <= 40_000`.
  - Added `@AGENTS.md` import directive generation to `generate_pointer_stub` in `src/devops_cli/ai/instruction_generator.py` for Claude Code memory loading.
- **Podman engine discovery & rootless sandbox user mapping (`devops docker`, `devops sandbox`)**:
  - Implemented automatic container engine discovery across `CONTAINER_HOST`, `DOCKER_HOST`, Docker contexts, rootless Podman (`$XDG_RUNTIME_DIR/podman/podman.sock` and `/run/user/<uid>/podman/podman.sock`), rootful Podman (`/run/podman/podman.sock`), and Docker default (`/var/run/docker.sock`).
  - Added fast configuration error when `CONTAINER_CONNECTION` is detected, guiding configuration to `CONTAINER_HOST`.
  - Added Engine API facts introspection (`kind()`, `is_rootless()`, `security_options()`) to identify Podman and rootless execution models.
  - Added user namespace mapping (`resolve_sandbox_user`) configuring `user="0:0"` on rootless engines so sandboxed workloads run with container root mapped to the host user, enabling write access to mounted workspaces without permission errors.
  - Enhanced Docker default socket connection failure message with Podman user socket activation instructions (`systemctl --user enable --now podman.socket`).
  - Handled Podman's BuildKit absence in `devops docker cache` with informative guidance directing users to `devops docker prune`.
  - Propagated resolved `DOCKER_HOST` to Dive container analysis and granted `XDG_RUNTIME_DIR` pass-through to Cosign image verification.

### Changed
- **Poetically Concise AGENTS.md**:
  - Condensed `AGENTS.md` from 116,655 characters (26,283 cl100k tokens, 497 lines) to 38,355 characters (8,839 cl100k tokens, 221 lines), achieving a 67.1% character reduction and 66.4% token reduction under the 40,000-character budget with 1,645 characters of headroom.
  - Linked operational procedures (release choreography, PR monitoring, review feedback loops) directly to canonical documentation (`docs/SDLC.md`, `docs/SELF_IMPROVEMENT.md`).
  - Replaced duplicate rules enforced by named checks with direct pointers to the enforcing commands and pre-commit hooks (`uv run devops ci`, `ruff-check`, `structural-invariants`).
  - Updated `CLAUDE.md` to load `@AGENTS.md` using Claude Code memory import syntax.
- **The roadmap service is suspended (`k8s/devops/roadmap-service`)**: GitHub suspended the Service's machine account, so `deployment/roadmap-service` asks for 0 replicas, and an Argo CD sync or `devops k8s deploy-stack --stack devops` no longer starts it. AGENTS.md and `k8s/README.md` open their roadmap-service sections with the suspension: nobody scales, restarts or re-pushes secrets for the Service, only a person runs mutating `devops roadmap` commands, and agents leave the Service's items labelled `status/blocked` alone.

### Removed
- **Unread syntopical and cognitive research settings**:
  - Removed dead constants and defaults (`DEFAULT_RESEARCH_DIR`, `DEFAULT_SYNTOPICAL_TIMEOUT_SECONDS`, `DEFAULT_SYNTOPICAL_MAX_SOURCES`, `CONST_RESEARCH_DIR_NAME`, `CONST_DEFAULT_MAX_SYNTOPICAL_SOURCES`, `CONST_SYNTOPICAL_MIN_RELEVANCE`, `CONST_SYNTOPICAL_MAX_EXCERPT_CHARS`) in `config/defaults.py` and `config/constants.py` with no consumers in `src/` or `tests/`.
- **Removed vLLM deployments, configuration, and leftover policies**:
  - Removed dead vLLM cluster URL defaults (`DEFAULT_VLLM_16GIB_CLUSTER_URL`, `DEFAULT_VLLM_48GIB_CLUSTER_URL`), settings field `AIConfig.vllm_url`, router method `GatewayRouter.scale_vllm`, CLI command `devops ai gateway scale`, and FastMCP tool `ai_vllm_scale`.
  - Removed vestigial vLLM Kubernetes manifests, perimeter policies, and port 8000 egress rules across `k8s/llm/` and `k8s/monitoring/`, including `k8s/llm/profiles/networkpolicy.yaml` (`vllm-profiles-perimeter`) and Portkey `vllm-backend`.
  - Removed vLLM server busy-share and waiting queue metrics from `devops ai gateway load` and pool load metrics calculation.
  - Updated `.devcontainer/devcontainer.json` Ollama endpoint to `http://ollama-16gib.llm.svc.cluster.local:11434`.
- **Legacy segment review engine & whole-file reviewer**:
  - Deleted legacy segment review engine and whole-file reviewer in `ai/review/runner.py`, leaving `ReviewPipelineOrchestrator` as the sole review pipeline.
  - Deleted dead `_run_persona_loop`, segment chunking, recompose functions, and `_save_findings_json` from `ai/review/runner.py`.
  - Deleted obsolete task prompts (`compose.md`, `paginated_review_protocol.md`, `path_review_prompt.md`, `review_output_instruction.md`).
  - Removed compose task: `ai.tasks.compose` configuration field, `AI_TASK_COMPOSE_*` settings, `DEVOPS_CLI_AI_TASK_COMPOSE_*` environment variables, `ReviewClients.compose`, and `PersonaDefinition.compose_prompt`.

### Fixed
- **AI model pricing snapshot merging, version invalidation, and tiered request pricing**:
  - Merged remote and custom partial pricing snapshots field-by-field onto bundled `genai-prices` dataset instead of replacing entire catalog.
  - Preserved token extraction for both unbundled and partial bundled providers after snapshot ingestion.
  - Recorded installed `genai_prices_version` and UTC `fetched_at` in snapshot metadata, falling back to bundled data with warning if versions mismatch.
  - Preserved recorded fetch timestamp as `auto_update_timestamp` on `DataSnapshot`.
  - Added `--reset` option to `devops ai cost update-pricing` to clear snapshot and caches, with mutual exclusion against `--source`.
  - Added `--format yaml` support, base-tier rate column headers, and table captions to `devops ai cost list-pricing`.
  - Calculated tiered request costs dynamically in `SpendGuard.record_usage` and `EmbeddingResult.cost` fallback, while honoring flat-rate caller pricing.
- **Cloudflare tunnel route synchronization and Kubernetes URL setup preservation**:
  - Preserved per-route `originRequest` configuration (`noTLSVerify`, `httpHostHeader`), custom catch-all ingress rules, and `warp-routing` settings during `devops cloudflare tunnel sync`.
  - Aborted tunnel sync on GET read failure without dispatching PUT updates, avoiding full config replacement and loss of existing routes.
  - Ensured `devops cloudflare tunnel sync --dry-run` performs zero network requests while outputting serialized GET and PUT request payloads.
  - Matched AI gateway ingress backends via `CONST_K8S_INGRESS_SERVICE_PATTERNS` using exact service-name and namespace matching rather than substring searches.
  - Protected pre-configured remote custom `ai.gateway_url` endpoints from being overwritten by discovered FQDNs in `_should_update_url`.
  - Guarded valkey host and port configuration from being overwritten when configured with a non-default port.
- **Review early exits & zero-model routing (`devops review`)**:
  - Exited `--summary` before `ReviewPipelineOrchestrator` construction, eliminating redundant model calls and preventing the creation of spurious session directories on disk.
  - Ensured diffs containing only routed files (such as `uv.lock`) or empty diffs with `--post` route through `_review_routed_files_only` with zero model calls and exit 0.
- **RAG collection embedding model recording, mismatch protection, and cosine score ranking (`devops ai rag`)**:
  - Recorded active `embedding_model` in payload for all indexed chunks across workspace and knowledge base indexing.
  - Refused indexing into collections holding points with a different embedding model or dimension, raising permanent `EmbeddingsError` with clear instructions to clear and re-index (`devops ai rag clear --force && devops ai rag index --force`) rather than wiping data.
  - Deleted `_handle_dim_mismatch` and prevented dimension mismatch from deleting or recreating collections during search, raising permanent `EmbeddingsError` naming collection and both dimensions.
  - Added process-level model verification on search to fail early when a collection was indexed with a different model.
  - Preserved raw vector cosine in `SearchResult.vector_score` while storing reciprocal rank fusion in `fused_score`, routing the reranker's vector signal through cosine score and rendering cosine beside final score in `devops ai rag query`.
- **Monitoring Service aliases removal & Chart-owned Service direct addressing (`devops k8s`)**:
  - Deleted plain manifest `k8s/monitoring/service-aliases.yaml` (`prometheus`, `kube-prometheus-kube-prome-prometheus`, `kube-prometheus-grafana`) to eliminate collision with Helm-managed chart Services during `deploy-stack`.
  - Repointed all Prometheus consumers directly at `prometheus-server.monitoring.svc.cluster.local:9090`: Alloy `localPrometheus` destination, Grafana Prometheus datasource, `prometheus-ingress` backend, and TLS certificate SANs.
  - Updated `configure-urls` and `port-forward` to target `svc/grafana` and `svc/prometheus-server` directly, removing obsolete `kube-prometheus-*` aliases.
  - Removed `kube-prometheus-stack-grafana` from candidate secret names in `fetch_grafana_password`.
  - Added repository-wide invariant guard test preventing plain manifest Services from sitting in Helm-managed namespaces without an explicit owned exemption.
  - Ignored `default` AppProject in `k8s/argocd/apps/projects.yaml` under `orphanedResources.ignore` to eliminate Argo CD `OrphanedResourceWarning`.
- **Knowledge base re-indexing on drift & Qdrant store inspection (`devops ai rag`)**:
  - Attached installed knowledge base digest (`sha256`), `embedding_model`, and `indexed_at` metadata to all stored knowledge base points in Qdrant collections.
  - Added autonomous lazy re-indexing before first retrieval across chat lookups, `devops ai rag query`, and MCP RAG tools whenever the collection holds zero knowledge base points or the recorded digest differs from the installed knowledge base, backed by a 30-minute failure cooldown and single warning.
  - Updated `devops ai rag drift` to inspect per-project Qdrant vector store point counts and knowledge base digests directly, reporting drift when collections are wiped in Qdrant even under an intact local cache.
  - Expanded `devops ai rag status` collection summary table to display point counts, embedding models, vector dimensions, knowledge base digests, and last indexed timestamps.
  - Emitted `devops_cli_rag_points` telemetry gauge on RAG retrieval use across monitored vector collections (#974).

## [0.2.33] - 2026-10-10

### Added
- Commands with a dry-run mode in the `ai`, `argo`, `devcontainer`, `docker`, `docs`, `grafana`, `k8s`, `prometheus`, `release`, `repos`, `review`, `ssh`, `telemetry`, `tf`, `tls` and `vault` groups now declare `--dry-run`, among them `devops tf apply`, `devops k8s configure-urls`, `devops release tag` and `devops vault logout`, so `devops <command> --dry-run` runs that mode where it used to fail with `No such option: --dry-run` (#412). Most of these commands print their preview and stop; `devops ai analyze path`, `branch` and `pr` still analyse, without the model, and print the metadata they would save, and `devops argo rollouts analyze` still evaluates its metric gate but does not abort the rollout.
- `devops release sync-notes --dry-run` prints the repository and the releases it would republish, then stops without reading any release from GitHub. With `--all` it names `<all published releases>` instead of listing them (#412).
- CI's static job uploads the SARIF of `devops scan report` to code scanning under category `/devops-scan` on every push and pull request, so each scanner's findings show on pull requests and close once fixed (#419).
- `devops review path`, `devops review branch` and `devops review pr` run mypy over the reviewed Python files and report its errors as findings (#873). mypy runs on the main worktree's `.venv` Python, or on devops-cli's own interpreter when the main worktree has none, with the reviewed tree's `pyproject.toml`, or else the main worktree's, as its config file. It runs only when the reviewed tree and the main worktree hold the same `uv.lock`, because a review never runs `uv sync` on a reviewed tree, so a project without a `uv.lock` gets no mypy findings. A branch or pull request review lists every mypy error in a reviewed file as introduced, since it does not type-check the base. The reviews also run Ruff under the reviewed tree's Ruff configuration, but no Ruff finding reaches `review.md` or `findings.json` yet: Ruff names each file by a `file://` URI, which the review does not match to a reviewed file. Both tools, like the complexity check below, run even when a review is given `--no-static-scan`, and neither is among the report's listed static analyzers, so the report does not say when one was skipped or could not run.
- `.devops/review.toml` takes `[advisory] rules`, the Ruff rules a review adds to the project's own selection, and defaults to `BLE001` (#873). Like Ruff's other findings, theirs do not reach `review.md` yet.
- `review.md` gains a `## Complexity` table of each function in the reviewed Python files whose McCabe complexity differs from the base, with its complexity before and after, `—` standing for a function that was added or removed (#873). Functions are matched by bare name within a file, so of several sharing a name, such as two classes' `__init__`, only the last is compared. The session's `findings.json` records the same rows as `complexity_delta`. A path review has no base, so it lists every function as added. A changed or added function that ends above `[complexity] max_complexity` in `.devops/review.toml` (default 10) is a MEDIUM finding, or HIGH above one and a half times that cap, and `[complexity] max_increase`, when set, also flags any rise of at least that much.
- `tests/test_swallowed_failures_ratchet.py` fails when a file under `src/` holds more swallowed failures than its ceiling in `tests/fixtures/swallowed_failures_ceilings.json`, where a file not listed has a ceiling of 0 (#1347). It counts Ruff's `BLE001`, `S110` and `S112` findings, and each call passing `check=False` that stands alone as a statement or is assigned to a name never returned, yielded or read for `.returncode`, `.stdout` or `.stderr`. The failure lists every site in each file over its ceiling as `file:line: rule` and says to handle the failures rather than raise the ceiling.
- A file under its ceiling also fails the test, which prints the command that locks the gain in, `uv run python tests/test_swallowed_failures_ratchet.py --lower` (#1347). That command recounts `src/`, lowers each such file's ceiling to its count, drops a file whose count reaches 0, and exits 1 without writing when any file is over its ceiling.
- `devops roadmap return <item>` hands a roadmap item back to refinement: with `--confirm` it posts an evidence comment on the issue and sets the item's Status on the board to New (#1348). The comment comes from `--comment` (`-c`), or from `--comment-file`, which replaces `--comment` when both are given. The command exits 1 on an empty comment, a missing comment file or an item that is not on the board. Without `--confirm` it prints the item's number and title, the target status and the comment, and writes nothing. `--dry-run` makes no request and prints the requests a run would make, and `--dry-run` with `--confirm` is refused.
- `AGENTS.md` asks for a feasibility check before any code or tests: the agent confirms the item's premise against the real system (upstream documentation, library source, live cluster state or the CLI at runtime) and records how in the task file's `**Feasibility**` field (#1348). When an item cannot be built as specified, or needs a refactor beyond its scope, the agent writes no compensating code: it comments on the issue with the evidence and a proposed re-scope, returns the item to New with `devops roadmap return`, and stops. Four signals call for stopping instead of adding code: a swallowed error, product code that detects tests, a second fix on top of a fix in the same area within one release, and a review loop that keeps finding new defects in the same feature.
- `.github/roadmap.toml` takes `release_slots`, the items a release holds above `release_cap` before a start trims it or a joining critical fix descopes one. It defaults to 4, and a negative value fails with an error naming the key (#1514).

### Changed
- `devops --dry-run <command>`, like a run with `DEVOPS_CLI_DRY_RUN` exported, now runs the command with `--dry-run` when the command it resolves to declares that option, instead of printing the generic `Would run delegated command:` line (#412). Unless the command line already gives `--dry-run`, it is added directly after the command path, ahead of the command's options, positional arguments and any `--`. A command that does not declare `--dry-run` still prints only the generic line and does not run, `-h` or `--help` shows the command's help, and `devops --help` says that a delegated command previews only if it declares `--dry-run`.
- `devops --dry-run <command>`, or a run with `DEVOPS_CLI_DRY_RUN` exported, now fails with a usage error and exit code 2 on an unknown subcommand instead of printing the generic line and exiting 0 (#412). So does a command that declares `--dry-run` given an option or argument it rejects, or missing a required one, such as `devops --dry-run release prepare` without a version.
- `docs/SDLC.md` requires state-mutating commands to declare `--dry-run` instead of using `@dry_run_command` (#412).
- `devops review verify` records a person's verdict as a label on the session's findings.json and candidates.json and nothing else; it ranks review history. A known false positive is a reviewed `[[suppressions]]` entry in `.devops/review.toml` with a reason and an expiry, and the six Semgrep false positives people had judged in the learned catalog are now such entries (#1150).
- Branch and pull request reviews and `devops pr check-readiness` list the unexpired `.devops/review.toml` suppressions whose path the change touches, in place of the mitigations ledger's perimeter warning (#1150).
- A persona's finding is reported unverified until a person judges it; `--no-persona-review` gives a tools-only review until the persona stage is removed (#1151). `devops ai prompt-eval` counts the verdicts the feedback dataset records per labeller, since the deterministic layer it replayed is gone (#1150).
- When `devops ai agents` has a model write `AGENTS.md`, in any repository, its prompt asks for a feasibility check before coding and for stopping with an evidence comment instead of adding compensating code (#1348). Its built-in template, used with `--template` or when no model answers, adds the feasibility check, the hand-back with `devops roadmap return` and the four stop signals only to the `AGENTS.md` it writes for devops-cli itself.
- The task-file template in `docs/agent/tasks/README.md` has a `**Feasibility**` line, and `tests/test_agent_task_files.py` fails any task file without one (#1348). Task files that predate the rule are exempt and are listed in `tests/fixtures/task_files_baseline.txt`.
- A release cut with no changelog fragment and no entries under its version's `CHANGELOG.md` section fails before it pushes, naming the version, its release branch, the missing section and, from `devops roadmap close` or the roadmap Service, the completed items with no fragment (#1450).
- `devops pr check-readiness` lets a pull request into a cut release branch edit `CHANGELOG.md` once the branch holds its version's section, which is how a critical fix after the cut adds its entry (#1450). A pull request into a release branch that changes `CHANGELOG.md` before the cut is still blocked, `docs/ROADMAP.md` stays the cut's, and a failed read of the branch's `CHANGELOG.md` is a blocker naming the error.
- `devops roadmap close --plan` lists `CHANGELOG.md` among the cut's files and the fragments the cut collects (#1450).
- `devops roadmap reprioritize` still fills a starting release to `release_cap` (12), but trims it only above its limit, `release_cap + release_slots` (16), so a P0 or P1 item placed in a release of 12 no longer moves another out (#1514). A critical fix that joins a started or cut release descopes its lowest-ranked unstarted item only once the release holds more than 16, and the size check descopes above the larger of 16 and the release's size at start. The `cap`, `over_size` and `trim` reason comments name the limit.
- The roadmap Service's refine job runs every hour and on a first run, as well as after a reprioritize run or an intake that placed a critical fix or a P0 item, so the items of upcoming releases are ready before those releases start. `devops roadmap refine` takes items nearest place first: the current release's New items, each planned release's New items, nearest release first, then the backlog's P0 and P1 items, each place by priority; the backlog's other New items follow while fewer than the configured `release_cap` items are Ready across the next planned release and the backlog. In a planned release and among the backlog's P0 and P1 items, refine also takes Ready items it has no record of, and sets one back to New, with a comment, when it finds it not ready. An item whose refine section a person edited no longer takes one of a round's places (#1515).
- The Service's `devops_cli_service_queue_depth`, `devops_cli_service_jobs_total`, `devops_cli_service_job_seconds_total` and `devops_cli_service_job_start_timestamp_seconds` series carry a `lane` label, `release` or `model`, beside `repo`, and so do its round-failure and worker-crash log lines (#1532). Every repository's model lane waits on the one background model, so a model-lane round runs longer the more repositories' model calls are queued; the model lanes are stalled only when none of them finishes a round for longer than every repository's refine rounds take together.
- `devops ci security` scans `src/` and `tests/`, the targets the repository's new `.bandit` names, at medium severity and above (#1542). `devops scan report` on a tree whose `.bandit` names its targets runs Bandit on them, as that file says, and honours the tree's `# nosec` markers, so the code-scanning upload reports exactly what the gate fails on; before, it scanned `tests/` and ignored `# nosec` while the gate scanned `src/` alone. A tree whose `.bandit` names no targets is still scanned whole, ignoring `# nosec`, and a review's scan still reads nothing from the reviewed tree and still ignores `# nosec`. The tests' Medium and High Bandit findings are fixed: temporary paths come from `tmp_path`, and a `# nosec` with its reason marks each literal that is itself under test.

### Removed
- `devops_cli.docs.command_resolver`; `devops_cli.core.command_resolver` replaces it (#412).
- The model verifier stage of `devops review path`, `branch` and `pr`, with its prompts `verify_finding.md` and `verify_finding_system.md`: no model gives a finding a verdict (#1150).
- The hallucination catalog, builtin and learned (`common_hallucinations.json`), the negative exemplars it showed the personas, and `devops review hallucinations list|remove` (#1150).
- The model-claim guards: the deterministic checks that invalidated a persona's claim (syntax, symbols, headers, the `mypy --strict` `None`-dereference probe, placeholder and unbacked advisories, the runtime floor, judged claims) and the adversarial-debate keyword filter (#1150).
- The construct validator and the executable-criteria runner; the criteria allowlist validator stays (#1150).
- The severity calibration caps and the location anchoring applied to persona findings, with the "Removed-Symbol Findings" report row and the "Executable Criteria" report section (#1150).
- `--no-verification` and `--verification-only` on `devops review path`, `branch` and `pr` (#1150).
- The `ai.tasks.verification` task and its `DEVOPS_CLI_AI_TASK_VERIFICATION_PROVIDER`, `_MODEL`, `_REASONING_EFFORT` and `_OLLAMA_URLS` variables (#1150).
- `--adjudicator`, `--perimeter` and `--regression-test` on `devops review verify`, and the MCP `verify_finding` tool, which recorded an agent's verdict (#1150).
- The mitigations ledger (`mitigated_findings.json`) (#1150).

### Fixed
- `devops ai benchmark --dry-run` no longer saves a task benchmark report to the `data.benchmarks_dir` directory (#412).
- The Prometheus server scrapes only itself and the OpenTelemetry Collector. Alloy, run by k8s-monitoring, finds every other target through annotation autodiscovery, `clusterMetrics.kubeDNS` and the Loki and DCGM integrations, so the unread API-server scrape (about 60% of head series) and four jobs that matched nothing are gone (#1130).
- The server's self-scrape carries the `cluster` label, which both remaining server jobs take from one anchor (#1130).
- `k8s/README.md` records which monitoring components run outside k8s-monitoring, and why (#1130).
- `[severity_caps]` in `.devops/review.toml` caps a scanner finding's severity by its path class at admission, for the reviewed head and the base revision alike. A secret scanner's finding, Gitleaks' or one of Trivy's secret results, keeps its severity; any other scanner's finding is capped, Bandit's B105 and Semgrep's credential rules among them (#1301).
- A `[[suppressions]]` path glob in `.devops/review.toml` covers files at any depth under a `**`: `tests/**` covered `tests/test_app.py` but not `tests/ai/review/test_runner.py` (#1150).
- The roadmap Service's cut (`devops roadmap close`, and `devops release prepare --create-pr`) collects `changelog.d/` into the version's `CHANGELOG.md` section and deletes the fragments in the cut commit, so `devops release check` passes on the release pull request's merge (#1450).
- Creating the CLI's tracer no longer runs `uname -p`: the `os.description` resource attribute is the system and release from `os.uname()`, where `platform.platform()` started a process the first time it was read. A dry run that created the tracer therefore started a process, depending on test order (#1450).
- `devops roadmap refine` keeps one `## Proposed design` section per item. The section it writes now ends in its end marker instead of `[end-marker]`, as it has since v0.2.26, so refining an item a second time, after a person edits its body, replaces the section instead of appending another; an end marker in the model's text is still neutralised. An item refined before this fix keeps its old section: refine adds one correctly marked section on its next run, then skips the item until a person deletes the old one (#1470).
- The roadmap Service runs each repository's close, reprioritize and metrics jobs in a release lane, and intake and refine, which call the model, in a model lane, each lane with its own worker and its own clone, so a slow intake or refine round no longer holds up closing a delivered item, cutting a release or starting the next one (#1532). Both lanes get every poll and webhook, and a GraphQL budget refusal in either holds both.
- A reprioritize success in the Service's release lane makes refine due at the model lane's next poll (#1532).
- `devops serve --service` hands its JSON logging to uvicorn as `log_config`, and uvicorn builds the service app once it has applied it, so the command no longer reconfigures the process's logging before the server starts (#1543).

## [0.2.32] - 2026-10-09

### Added
- Pull requests show changed-line coverage against their base branch (diff-cover), plus any added `pragma: no cover` lines, in the Tests & Coverage job summary. The report is advisory and sets no coverage threshold (#850).
- pytest-randomly 5.0.0 joins the dev dependency group. `addopts` blocks it with `-p no:randomly`, so `pytest`, `devops ci` and every other run keep file order, and `uv run pytest --co -q` collects the same order as before (#852).
- `devops ci test --repeat N --seed S` runs the selected test files N times, one run after another on one process (`-n 0`), each shuffled by pytest-randomly with seeds S to S+N-1. S defaults to a seed derived from HEAD's commit hash. The first failing run stops the command and prints its seed with the command that reproduces it. `--repeat` refuses a run that no test file narrows, since shuffling the whole suite waits for thread-leak isolation (#852).
- The advisory **Changed-Test Independence** pull-request job in `ci.yml` runs `devops ci test --repeat 3` over the pull request's added or modified test files, and skips its toolchain and test steps when no test file changed (#852).
- `devops ci mutate [PATHS] [--changed] [--base REF]` mutation-tests functions with mutmut 3.8 on demand (#853). With `--changed` it maps the functions the working tree changed since its merge base with `--base` (default `main`), untracked files git does not ignore included, to mutmut's names, and a `--base` naming no commit is an error; PATHS alone select every function in those files. mutmut runs the tests covering each function in its own process, with xdist off, and the command shows each mutant no test killed, with its diff, then the killed, survived, timeout and no-tests counts. It prints no score, exits 0 whatever survives, and is neither a `devops ci` stage nor a `ci.yml` step. The first run mutates the whole source tree into the git-ignored `mutants/` and runs the test suite once, serially; later runs reuse it, and `rm -rf mutants` resets it.
- An architectural invariant fails on any `# pragma: no mutate` under `src`, so no line exempts itself from mutation (#853).

### Changed
- The settings parser refuses scheme-less URLs for `argocd.url`, `grafana.url`, `ai.ollama_urls`, and `OLLAMA_BASE_URL` with a prescriptive `ConfigurationError` instead of prefixing `http://`.
- The network probe refuses targets lacking a host name or carrying invalid ports with a `ValidationError`.
- The embedding benchmark refuses unrecognised endpoints under a gateway provider, requiring `--provider` to benchmark external endpoints.
- Sandbox whitelist parsing refuses entries containing empty port suffixes (`example.com:`, `example.com:/path`).
- Failed repository clones wrap `gitlib.GitCommandError` into `GitOperationError` and report masked stderr from git and OpenSSH without exposing credentials.
- Pinned GitHub host keys are seeded across all clone operations, including HTTPS clones.
- The release no longer pins, bumps or pre-publishes the Service image's tag; Argo CD Image Updater rolls the Service onto `service:latest` (#1486). A release pull request's CI now builds, smoke-tests and scans the Service image without pushing it. On the merge to `main`, `release.yml` builds the image, scans it, pushes it by digest and attests its provenance, then tags it `vX.Y.Z` and `latest`, and Image Updater moves Application `devops` onto the new digest within one poll, with no git commit.

### Removed
- In-process `known_hosts` parser and runtime `ssh-keyscan` invocation, delegating host key validation to OpenSSH.
- The release cut's bump of the Service image's `newTag` and its rewrite of the Argo CD git sources' `targetRevision` (#1486).
- `devops release check`'s checks of the Service image pin and of the Argo CD `targetRevision`s (#1486).
- The `images:` pin in `k8s/devops/kustomization.yaml` (#1486).
- Service image publishing from `release/vX.Y.Z` in `release.yml`, with its publication plan and the step that pointed `latest` at an image the release branch published (#1486).

### Fixed
- The `devops review` command tests no longer start the Logfire SDK's token-check thread, which printed the "Logfire API is unreachable" warning on every run and made the dry-run socket-recorder test flaky. The tests read the per-test config instead of a `MagicMock` settings object, and a background thread that dies with an exception now fails the test run (#965).
- The ollama tier DaemonSets no longer run ollama as root: every tier runs it as UID and GID 10001 with RuntimeDefault seccomp, no privilege escalation, all capabilities dropped and a read-only root filesystem, with `/tmp` on an emptyDir (#1060). `HOME` is `/home/ollama`, so the key and models stay on the hostPath `/var/lib/ollama` and nothing is downloaded again. A root initContainer, `own-model-directory`, holding `CAP_CHOWN` alone, gives that directory to UID 10001 at every start, because `fsGroup` does not apply to hostPath volumes; it is the one `run-as-non-root` exception kube-linter reports, recorded in the manifest and `k8s/README.md`. `test_every_ollama_tier_runs_unprivileged` pins these settings for all 9 tiers.
- Kubernetes service, node, LoadBalancer, and telemetry collector URL builders bracket IPv6 host addresses using `httpx2.URL`, preventing URL parser failures.
- `configure-urls` handles IPv6 cluster endpoints and falls back safely to loopback when endpoints are unreachable, including port-80 LoadBalancers.
- Kubernetes Service proxy addressing validates namespace, service, and port identifiers and refuses dot segments (`..`, `.`, `%2e%2e`), preventing path traversal and credential leakage beyond the Service boundary.
- Target resolution for Kubernetes API proxies preserves server path prefixes, raw URI encodings, and cleanly separates connection base URLs and path prefixes.
- Sandbox network probe targets using `https://` are probed over HTTPS with paths appended via `append_path`, preserving path queries and IPv6 bracketing.
- URL, endpoint, and authority reads across benchmark runners, docs ingester, telemetry exporters, vulnerability lookups, and pricing now use sending client parsers (`httpx2.URL` and `read_url_or_authority`), preventing scheme sniffing and port mismatch bugs.
- Benchmark key trust boundaries compare canonical URL origins through `httpx2.Origin`, preventing trust boundary leaks and ensuring consistent host evaluation.
- The documentation crawler normalizes link resolution and origin checks using `httpx2.URL.origin`, preventing scheme downgrades and SSRF boundary escapes.
- OTLP telemetry client preserves explicit collector schemes and endpoints, preventing invalid gRPC port conversions and TLS configuration errors.
- Vault broker URI parsing respects scheme case-insensitivity and preserves fragment separation.
- Prometheus keeps every series node-exporter serves (no allow list; its collector flags decide what is collected), so Node Exporter Full and the Kubernetes node dashboard show data again (#1129).
- The `alloy-singleton` collector runs as one Deployment pod through the chart's `singleton` preset instead of a DaemonSet per node, so Kubernetes events are watched and shipped once (#1129).
- Alloy writes the cluster name to Prometheus once, as `cluster`, without the duplicate `k8s_cluster_name` label (#1129).
- `kube_hpa_labels` is removed from the kube-state-metrics allow list, since kube-state-metrics v2 never serves it (#1129).
- CI jobs name their runner image, `ubuntu-24.04`, instead of `ubuntu-latest`, and uv in `ci.yml` and `release.yml` uses only its own CPython builds (`UV_MANAGED_PYTHON`). GitHub moves `ubuntu-latest` to Ubuntu 26.04 from 2026-10-19, where uv would have used the image's own Python 3.14 instead of the 3.14.7 that `.python-version` pins. The move to `ubuntu-26.04` waits for the workflow linter to accept the label (#1501) (#1494).
- CI's and the release's Service image scans run Trivy 0.75.0, the version `tools.lock` pins for `devops install-tools`, instead of 0.70.0, and a workflow contract test fails whenever an `aquasecurity/trivy-action` step's `version` differs from the lock (#1499).

### Security
- The host sandbox no longer declares a noexec `/tmp` that bubblewrap never applied (#798). Bubblewrap has no noexec option for a tmpfs, so the host policy now declares only the 64 MiB size, and the container sandboxes keep their `size=64m,noexec` policy. A host sandbox whose policy declares a tmpfs option bubblewrap cannot apply, such as `noexec` or `size=50%`, now fails at construction with an error naming the option, instead of dropping it. SECURITY.md now says that the host sandbox's `/tmp` allows execution.
- The output-cap test now runs a writer that ignores SIGPIPE and checks that the sandbox kills it at the cap within 1 s, well before its timeout (#798).
- GitHub clones append GitHub's published host keys directly to `~/.ssh/known_hosts`, ensuring junk known_hosts lines no longer skip pinning and failed keyscans no longer skip host-key verification silently.

## [0.2.31] - 2026-10-09

### Added
- `deptry` quality gate step enforcing that `pyproject.toml` declares all directly imported dependencies and flags unused or transitive packages (#1120).
- Argo CD Image Updater keeps the `devops` Application on the digest `ghcr.io/dan-petty/devops-cli/service:latest` points at. Application `argocd-image-updater` installs the argo-helm chart pinned to 1.3.1 in namespace `argocd`, and its one ImageUpdater (`k8s/argocd/image-updater-values.yaml`) writes `service:latest@sha256:<digest>` into the Application's `spec.source.kustomize.images` within one 2-minute poll of `latest` moving, with no git write-back. roadmap-service and CronJob `devops-cli` roll onto a release once `release.yml` points `latest` at it, and the `newTag` pin in `k8s/devops/kustomization.yaml` no longer decides the running image. `k8s/README.md` shows how to read the deployed digest (#1485).

### Changed
- Test worker startup latency and test collection time reduced by ~25% (saving 9.50s on 16 workers, and 11.27s on the full test run) by deferring heavy LLM and vector client SDK imports (`anthropic`, `google.genai`, `kubernetes`, `qdrant_client`, `openai`) across `devops_cli.ai` agents, models, and provider packages until first use (#1338).

### Removed
- `Timeout` re-export removed from `devops_cli.ai.settings` and `devops_cli.ai.agents`; `create_model_settings` and `resolve_runtime_model_settings` accept numeric seconds as `float | None` (#1120).
- **Unauthenticated Git daemon service and port 9418**:
  - Removed the background Git daemon service stub and its step from `devops devcontainer post-start`, eliminating unauthenticated serving of repository clones under `repos/` on port 9418 (#1122).
  - Dropped `DEVOPS_GIT_DAEMON_AUTOSTART` and `DEVOPS_GIT_DAEMON_PATHS` configuration environment variables (#1122).
  - Dropped port 9418 forwarding and attributes from `.devcontainer/devcontainer.json` and the devcontainer template, and removed port 9418 egress from Argo CD network policy (#1122).

### Fixed
- The durable-run store (`durable_runs.db`), Kubernetes port-forward daemon state file (`k8s/port_forwards.json`), and docs-ingestion directory now resolve their default paths through `resolve_store_path` under the repository data directory, respecting `DEVOPS_CLI_DATA_DIR` and `data.dir` settings instead of resolving relative to the working directory. An architectural invariant prevents direct `.data` path construction across `src/` (#1036).
- Test consoles render CLI help at the conftest width (`COLUMNS=250`) in every environment by preventing Typer's GitHub Actions detection from forcing an 80-column terminal under `TERM=dumb`, eliminating width-dependent test discrepancies between local runs and GitHub Actions CI (#1041).
- `devops docker push` now supports custom registry endpoints with port specifications (e.g. `localhost:5000/app:1.0`, `example.com:443/app:1.0`), delegating repository validation directly to docker-py and the daemon while safely escaping progress output (#1108).
- Prevent credential leakage in `SSRFBlockedError` details by masking single target URLs before bounding string length, eliminating legacy string partitioning (#1109).
- Ensure deduplication and correlation produce identical finding sets and cluster sequences regardless of input order across all permutations (#1141).
- Enforce complete linkage in correlation clustering so findings only join when correlating against every cluster member, leaving 2 clusters for bridging-first chains (#1141).
- Select cluster representatives and scalars deterministically using highest severity, narrowest parsed region span, and total finding key, sorting locations numerically (`a.py:9` before `a.py:10`) (#1141).
- Tests touch no state outside temporary directories: each pytest worker process runs with an isolated home under pytest basetemp before devops-cli is first imported, with a git identity on `example.com` (#1311).
- TLS test passes `--tls-dir`, user data root resolves through `DEVOPS_CLI_USER_DATA_ROOT` across `git/worktree.py`, `core/repo.py`, and `tools_lock`, and worktree tests assert paths stay under `tmp_path` (#1311).
- The Ollama round-robin index lives under `DEVOPS_CLI_DATA_DIR` instead of the system temp directory, and `tempfile.gettempdir()` resolves under `tmp_path` for every test (#1311).
- The floor's patches of `CONFIG_PATH` and `CONST_USER_DATA_ROOT` in `tests/conftest.py` are removed (#1311).
- The session workspace tripwire verifies that worker homes leave no state at devops-cli's locations (`CONST_CONFIG_DIR`, `CONST_USER_DATA_ROOT`, `DEFAULT_SSH_KEY_DIR`, `DEFAULT_LOCAL_BIN_DIR`) and fails the session naming each leaked path (#1311).
- `k8s/otel/networkpolicy.yaml` rule 4 now admits Traefik on TCP 8888, allowing the `otel-metrics-ingress` route to reach the OpenTelemetry collector through Traefik (#1371).
- `devops k8s deploy-stack` now deploys both `argocd/networkpolicy.yaml` and `otel/networkpolicy.yaml` natively under the `infra` stack manifests, removing both exemptions from the undeployed network policy guard suite (#1371).
- **Docker sandbox and test sandbox dry runs validate the workspace**:
  - `devops docker sandbox --dry-run` and `devops test sandbox --dry-run` now validate the workspace directory via `WorkloadSandboxRunner.build_dry_run_details()`, refusing forbidden roots, home directories, socket directories, and sensitive paths with `DockerSandboxError` before executing any commands or container engine calls (#1383).
  - Preserved request-free dry-run behavior for remote tcp engine hosts (`DOCKER_HOST`) without DNS egress lookups or container client dialing (#1383).

### Security
- **Finding fingerprint and run-store digest regression pins**:
  - Pinned finding fingerprints (`NormalizedFinding.fingerprint`) across multiple scanners, symbols, and canonicalisation formats to literal 32-character SHA-256 hashes, ensuring algorithm changes cannot silently invalidate suppression policies (#855).
  - Pinned `CONST_SARIF_FINGERPRINT_KEY` to `"devopsCli/v1"` with regression tests enforcing version bumps on any algorithm changes (#855).
  - Added golden OASIS SARIF 2.1.0 report (`tests/golden/sarif_report.json`) validated against schema and asserted against SARIF emission output (#855).
  - Pinned run-store content digests (`run_store.digest`) to literal 16-character SHA-256 hashes for primitive and nested payloads, preventing baseline key orphaning (#855).
- The Docker daemon endpoint check now covers the exact endpoint the SDK dials, resolving endpoints in priority order across `DOCKER_HOST`, `DOCKER_CONTEXT`, `currentContext` in `config.json`, and the default socket. Uppercase schemes, bare address-and-port endpoints (e.g. `192.0.2.1:2375`), and Docker-context TCP endpoints are now validated against SSRF egress policies, requiring `ai.allow_private_network` for private network targets. Missing contexts now fail fast with an informative error instead of silently falling back to the default socket (#1108).
- Standardize URL credential masking and redaction on library parsers (`urllib.parse` and `httpx2`), covering arbitrary schemes (`postgres://`, `redis://`, `mysql://`, `custom://`, `http://`, `https://`), passwords containing `@`, `#`, or `/`, and empty-username URLs (`redis://:pw@...`, `http://:secret@...`) while keeping IPv6 host brackets intact and preserving original `http://` schemes without rewriting (#1109).
- Introduce the `<masked-url>` fail-closed placeholder for whole URLs that cannot be parsed safely or contain anomalous userinfo delimiters (#1109).
- Sanitize OpenTelemetry collector endpoints via strict parsing and IP classification, masking private, CGNAT, link-local, and documentation IPs to the URL-safe `internal-ip` placeholder (#1109).
- Strip userinfo credentials from gateway `served_by` headers (`x-litellm-model-api-base`) across both blocking and streaming LLM responses before storing into the spend ledger, event payloads, and trace span attributes (#1109).
- Migrate `devops scan` and `NormalizedFinding` to Fingerprint v2 (`devopsCli/v2`), hashing tool, rule ID, repository-relative path, enclosing qualified symbol from AST, and a 100-character non-whitespace window starting from the flagged line, with occurrence indexing for collisions (#1141).
- Identify region-less findings via SARIF `logicalLocations` (`kind/namespace/name[/container]` for Kubernetes resources, `purl@version` for dependency advisories) (#1141).
- Dropped the `0.0.0.0/0` ingress peer from `k8s/argocd/networkpolicy.yaml` and `k8s/otel/networkpolicy.yaml`, admitting Traefik by its selector instead of world CIDRs that admitted every pod in the cluster under kube-router. Argo CD's API-server egress now admits TCP 6443 through an `ipBlock` peer with cloud metadata SSRF protection, allowing GitOps reconciliation against the Kubernetes API server (#1371).

## [0.2.30] - 2026-10-09

### Added
- `devops sandbox network-policy --allow-collector` and `sandbox_network_policy(allow_collector=True)` add one egress rule to the OTel collector's pods: the `otel` namespace and the `opentelemetry-collector` / `otel-collector` pod labels together, on TCP 4317 and 4318, with no `ipBlock`. It applies to the `sandbox_namespace`, `public_whitelist` and `local_whitelist` modes; with `isolated` or `bridge` the command exits 1 naming those modes (#702).
- Sandbox containers and execs carry trace context: with telemetry enabled, `devops sandbox deploy`, `devops docker sandbox` and `devops test sandbox` give the container `TRACEPARENT` (and `TRACESTATE` when set) parented to the `sandbox.deploy` or `docker.workload_sandbox.run` span, and each `devops sandbox exec` runs in its own `sandbox.exec` span and passes that span's context to the command. `DockerEngineService.exec_in_container` takes `environment`. The configured env is not changed, and with telemetry disabled the container's environment is exactly the configured one (#702).
- `devops review score SESSION... --labels FILE [--json]` scores saved review sessions against a label file, offline: lenient, strict and per-distinct-defect precision split by producer, VERIFIED and HIGH/CRITICAL precision, recall against the label file's recall set and against its input's known defects, and stability across sessions of one input digest (the mean pairwise Jaccard of their identities and Fleiss' κ of their statuses over the identities every one reported). Every ratio shows its n; a ratio over a row no label covers reads "not computable", and those rows are listed. A SESSION without a readable findings.json is refused, and a session that records no input digest is compared with no other. Each score is kept as a `review-score` run, which names each figure it could not compute and why (#1138).
- A row's identity is its cluster in a session the label file maps row by row; otherwise the `fingerprint_v2` of the findings.sarif result at its cited file and line, else that result's tool, rule, path and line or object, and results of more than one tool, rule or fingerprint at that place leave the row unlabelled; otherwise, for a model's row, the one label of its path and origin page within five lines. Nothing is read from a title. Stored absolute paths are made relative to the input's checkout, a row outside the session's reviewed tree counts as false, and a row echoed from a fixture page is no recall (#1138).
- `tests/fixtures/review_labels/labels.json` holds the seed labels of S11 and the ten loop sessions (S12–S21): a row map of all 492 findings.json rows and 169 labelled clusters, transcribed from the loop study. Scored, they give S11 12/51 lenient, 11/51 strict and 4/30 per distinct defect, and the loop 75/441 and 49/441 (#1138).
- `devops review score --materialise-golden DIR` writes the golden set's files into a git repository with one fixed commit, for a path review, and lists the 12 golden defects no tool can express as accepted recall loss. It refuses a DIR that is a file and a golden file under `.git/` (#1138).
- `devops ai runs check` takes `--max-precision-drop` and `--max-stability-drop` for review score runs, and `--max-calls-increase` for model calls, a review's cost. A precision or stability figure the baseline recorded and the run could not compute, such as precision over a new unlabelled row, fails the check and reads "not computable"; model calls are judged when both runs record them (#1138).
- ADR 0005 records that review findings come from tools and checked facts while models explain and plan, and `docs/VISION.md` item 8 becomes Evidence-First Code Reviews (#1138).
- Dependency: statsmodels 0.15.0, with scipy, pandas, patsy and formulaic, for Fleiss' κ; it is imported only when a score computes κ (#1138).
- `tools.lock` (`src/devops_cli/tools_lock/`) names every tool `devops install-tools` installs, at an exact version: kubectl, kustomize, helm, argo, argocd, kubectl-argo-rollouts, trivy, kube-linter, popeye, pluto, k9s, gitleaks 8.30.1 and osv-scanner 2.6.0 as binaries with a SHA-256 per platform (linux and darwin, amd64 and arm64), and Semgrep 1.179.0 and Bandit 1.9.4 as Python tools whose requirements files `uv pip compile --generate-hashes` writes (#1142).
- `devops install-tools` installs gitleaks, osv-scanner, Semgrep and Bandit. A Python tool installs with `uv pip sync --require-hashes` into a relocatable virtual environment of its own. uv runs with `--no-config`, so a `uv.toml` or `[tool.uv]` in the current directory cannot change the install, and keeps `UV_MALWARE_CHECK`, `UV_CACHE_DIR` and `UV_LINK_MODE` from the environment (#1142).
- `devops install-tools --check` installs nothing: it lists each tool whose command is not linked at its locked version and exits 1 if there is one (#1142).
- `profile.json` records `tools_lock_digest`, the digest of the tools lock a review started with, and `code_changed_during_run`, true when devops-cli's own checkout got a commit or an edit while the review ran; the review then prints a warning (#1142).

### Changed
- A whitelist entry opens one TCP port: the port it names (`scheme://host:port`, `host:port`, `[v6]:port`), else 443 for a bare host, IP or CIDR or `https`, and 80 for `http`. An entry that named no port used to open every port, and a local entry such as a bare private address now opens only 443. An entry with another scheme and no port, a port outside 1-65535, and an entry with a path but no scheme (such as `140.82.112.0/20:8443`) are refused with an error naming the entry, and the command exits 1. This is a deliberate break, with no fallback to the old rule (#702).
- `devops scan complexity`, MCP `scan_complexity` and the inspection hotspots report standard McCabe complexity, as Ruff's `C901` counts it: `assert`, `with`, conditional expressions and boolean operands add nothing, and a closure counts toward the function that defines it as well as on its own. At a cap of 10 the scan now flags the same 54 functions in `src/` that `ruff check` does, where it flagged 244 (#773).
- The `structural-invariants` pre-commit hook counts nesting as CI does, the function body being depth 1, so 5 nested blocks now fail at commit (#773).
  - It runs from `devops_cli.core.code_metrics`, the one copy of the metric, with its cap passed as `--max-depth 5`, and loads no scanner and no pydantic-ai: a run over one file takes about 0.6 s instead of 8.5 s under the same load.
  - `devops ai spec`'s indentation rule reads the same metric: an `except`, `match`, `assert`, `async for` or `async with` block now opens a level, and a `try` body no longer does.
- `devops ai runs check` also fails a run whose model calls rose more than its `--max-calls-increase` (default 20%) over the baseline's, for any two runs that both record calls, review benchmarks included (#1138).
- `docs/SELF_IMPROVEMENT.md`'s recall protocol scores its samples with `devops review score` in place of an inline `score_recall.py` script. It counts reported rows only: it no longer counts the candidates before re-ranking and verification, so its bar counts a sample that reports a set finding, not one that only found it (#1138).
- Each tool version installs under `~/.local/share/devops-cli/tools/<name>/<version>/`, and its commands in the target directory link there. Once they do, the tool's other version directories are removed, so a pin bump leaves no old build or virtual environment behind (#1142).
- `devops install-tools` exits 1 when any tool does not install, such as a build refused for its checksum; it used to print the error and exit 0 (#1142).
- Post-create installs Semgrep from the tools lock with the other managed tools, in place of its own `uv tool install semgrep`, so only one Semgrep is on PATH. Its `semgrep` and `pysemgrep` both link to the locked environment, because `semgrep` runs the `pysemgrep` it finds on PATH, and they replace the links `uv tool install` left (#1142).
- `devops install-tools --only-missing` installs each tool whose command is not linked at its locked version; it used to skip any tool found on PATH (#1142).
- `devops install-tools status` makes no request. It shows each tool's pinned version and whether its command is at the pin, another path PATH finds or not installed, in place of the latest release (#1142).

### Removed
- `devops_cli.security.structural_invariants`, and `analyze_file_complexity` and `FileComplexityReport` from `devops_cli.security.complexity`; `devops_cli.core.code_metrics` replaces them (#773).
- `devops install-tools` no longer looks up any tool's latest release, and its `--version` option is gone: the lock is the only version source. `validate_version_str` and the per-tool download URL constants go with it (#1142).

### Fixed
- `devops branches jira` now creates and checks out the feature branch; it always failed on `git checkout -b -- <name>`. When git refuses the branch, the command prints git's reason and exits 1 instead of a traceback (#900).
- kube-linter findings carry their own check, message, remediation, manifest file and object. kube-linter writes `Check` and `Remediation` beside `Diagnostic`, but the adapter read the check from `Diagnostic`, so every finding was titled `[kube-linter-check] K8s Security Lint Warning`, and a directory scan located each one at the directory. A finding is now titled `[<check>] <message>`, so the check is its rule id and SARIF `ruleId`; its fix is kube-linter's remediation; it is located at `<manifest>:<Kind>/<namespace>/<name>`, or `<Kind>/<name>` when the manifest names no namespace (no `default` is guessed); and its category is the class the check or the message names, else `security_misconfiguration`. `devops k8s lint` prints the check in its Title column: the table did not escape its cells, so Rich read `[<check>]` as a markup tag and dropped it (#1045).
- `devops scan report` keeps every finding and lists findings on different objects as separate rows: the fingerprint and the correlation key include the finding's object when it has one. Over the 7 kube-linter reports of `k8s/` at da50329 (4 checks, 3 files) the report kept 1 and now keeps 7 under 4 rules, and two Popeye issues on two resources of one sanitizer were 1 and are now 2. Each `--json` cluster names its object in `symbol`, as each finding does. A review keeps two kube-linter checks on one object as two candidates (#1045).
- Every symbol-located finding (Trivy, Pluto, Popeye, Dive, kube-linter) gets a new fingerprint and SARIF `partialFingerprints` value once, so a fingerprint suppression of one must be recorded again. A suppression by rule `kube-linter-check`, in a scan policy or `.devops/review.toml`, must now name the check. A finding without a symbol keeps its fingerprint (#1045).
- A multi-line result (`path:start-end`, as Semgrep writes it) reads as its start line instead of a symbol named by the range, and a location of only `:<line>` reads as that line, so both keep their fingerprints when an edit moves them (#1045).
- The knowledge base's RAG article no longer says reviews ground on whatever the index holds: a review asks the index for each page by its file path and symbol names, and for each finding it verifies by the finding's title and description, and writes nothing to it (#1138).
- A web_fetch result cut by its budget inside a code block now closes the block before the truncation note and the closing `</untrusted_web_page>` tag (#1298).
- `devops docs check` validates an option written inside optional-group brackets (`[-v <ver>]`, `[--json]`) instead of skipping it as a placeholder, so a misspelled option in a synopsis fails the check (#1299).

### Security
- **Sandbox NetworkPolicy egress is scoped per entry and port (#702).** `devops sandbox network-policy` and MCP `sandbox_network_policy` emit one egress rule per whitelist entry, with that entry's addresses and its one TCP port, so no address is opened on every port or on another entry's port. Before, all whitelist addresses shared one rule with no `ports`, which opened every port and protocol to them.
- A public whitelist CIDR is refused when it overlaps a non-public block, not only when its ends are non-public: `is_non_public_ip` treats a range as non-public when it overlaps one of pydantic-ai's non-public blocks or a private IPv4 block's NAT64 (`64:ff9b::/96`) or IPv4-compatible (`::/96`) image. `8.0.0.0/5` (which holds 10.0.0.0/8), `64:ff9b::800:0/101`, `::800:0/101` and `64::/16` are refused; `2606:4700::/48` and `140.82.112.0/20` are still admitted (#702).
- FastMCP's DEBUG log of each tool call and prompt request no longer records its arguments. With `FASTMCP_LOG_LEVEL=DEBUG`, a `vault_set` call wrote its `key_values` to stderr; the record now names the tool or prompt and reads `<redacted>` in place of the arguments (#899).
- `devops config audit-keys` no longer prints a config line it cannot parse, which could hold a secret: its warning names only the file, the error class and the line and column. A file it cannot read or parse is reported as unaudited rather than clean, is listed under `unaudited_config_files` in `--json`, and makes the command (and the MCP `config_audit_keys` tool) fail with exit 1 (#1022).
- No tool installs unverified any more. kube-linter installed with no checksum, and trivy, popeye, pluto and k9s installed with only a warning when their checksum file could not be fetched; every build is now checked against the lock's SHA-256 and refused on a mismatch (#1142).
- A sandbox workspace can no longer hold the user's SSH agent socket or the X11 socket directory (#1384). `devops docker sandbox`, `devops test sandbox`, `devops sandbox deploy` and the MCP tools `docker_sandbox` and `sandbox_deploy` now also refuse a workspace that is, or holds, either of these directories, and the refusal names the workspace and the directory:
  - the directory of the socket `SSH_AUTH_SOCK` names, and, when that socket is a symlink, the directory it leads to. This includes VS Code's `/tmp/vscode-ssh-auth-*.sock` when VS Code sets `SSH_AUTH_SOCK`;
  - `/tmp/.X11-unix`, so a workspace of `/tmp` is now always refused.
- A workspace under either directory is still mounted, and an unset or relative `SSH_AUTH_SOCK` adds no rule.
- `mask_secrets` masks GitHub user tokens (`ghu_`), installation tokens (`ghs_`) and refresh tokens (`ghr_`) as well as `ghp_`, `gho_` and `github_pat_`, including the new installation tokens of about 520 characters, which contain dots (Actions' `GITHUB_TOKEN` among them). Before this change a `ghs_` token in a pre-receive hook's message would have reached the release command's error output unmasked. A prefix that follows a letter, a digit or `_` is part of a longer word, such as a snake_case test name, and is now left as written for every prefix, so code names are no longer rewritten before review (#1398).

## [0.2.29] - 2026-10-08

### Added
- **`devops vault logout`**: revokes the token `devops vault login` stored, at the address and namespace that issued it (`auth/token/revoke-self`), then deletes it from the OS keyring. The local copy is deleted even when Vault is unreachable or the token has expired, and the output says the revoke did not happen (#709).

### Changed
- A token an earlier `vault login` stored as a bare string is no longer used; run `devops vault login` again (#709).
- `devops gh secrets sync --source vault --dry-run` no longer reads Vault: it lists each secret it would read, seal and upload, so the dry run sends no request (#709).
- `devops gh project sync` and `devops gh project reconcile` add no card: an issue reaches the board through `devops roadmap intake`, and a pull request gets no card, its progress showing on its issue's card. New pull requests no longer get board cards, and sync no longer adds the repository's open issues. Reconcile reports how many open issues wait for intake (#892).
- `devops gh project reconcile --plan` reads the board and the repository and lists the changes; `--dry-run`, and the global dry run, make no request and list the requests a run makes. MCP `gh_project_reconcile` takes `mode` (`dry-run`, `plan` by default, or `write`) in place of `dry_run`, so a call with no arguments no longer writes (#892).
- `devops gh project sync` reports the fields it created and reconcile's outcome, prints reconcile's stop line and exits 1 when reconcile stops early or does not start, and its dry run makes no request and prints no board number (#878, #892).
- Every `devops gh project` and `devops gh views` `--template` option defaults to `.github/project-template.json` at the repository root, so the commands work from a subdirectory; `reconcile --project-number` reads the board's own Status options and loads no template (#1010, #892).
- `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` is read only through `ai.allow_private_network`, when a client is built: `validate_url`, the LLM client and the HTTP broker no longer parse the variable themselves, and the broker no longer freezes it at import. A check made with `allow_private=False` stays public-only, and an `AIConfig` built in code (an agent given a model name, `model_request_sync`, the chaos fallback, `GatewayRouter()` with no config) takes its own `allow_private_network` rather than the variable (#898).
- `new_http_client` and `new_async_http_client` take a required `level` and own `verify`, `http2` and `limits`; tenacity retries are opt-in with `retries=`, because the retry transport turns every 4xx and 5xx into an error. `HttpClientBroker` keeps one client per level, and `request`, `arequest`, `new_client`, `get_client` and `get_async_client` take the level; every Vault request (`vault_request`) uses the private level. `get_shared_client` and `get_shared_async_client` take the level, which is part of the pool key, so a connection never crosses levels (#898).
- The LLM client builds its clients at the configured level, loopback or private when `ai.allow_private_network` is set, and raises when one cannot be built instead of falling back to a client without the retry transport (#898).
- The broker's request hooks check only a request's own egress policy and the scheme; the async hook no longer runs a blocking DNS lookup on the event loop (#898).
- `httpcore2` and `anyio` are declared dependencies, at the versions already locked, and `h11`, which the test fakes use to write and read HTTP/1.1, is a declared dev dependency (#898).
- A release whose pull request has merged, and whose GitHub Release is not published yet, is now `merged` (`ReleaseState.MERGED`) instead of cut, as the reprioritize plan's "Current release" line shows. A critical fix filed then goes first into the next release, with a "the release pull request of vX.Y.Z has merged" comment, and the start of a release a person cut early, its pull request open or merged, still pulls nothing in (#1294).
- `plan_intake` and `intake_candidate` take the repository they run on (`repo`), which `devops roadmap intake` and the Service's intake job pass (#1358).
- The intake `--dry-run` request plan lists the `.github/labels.yml` read first among the candidate reads, before the timeline reads and the embedding call, with the condition that the run has a candidate; for a `--title` candidate it has no condition (#1358).
- `devops roadmap intake --limit N` decides the N oldest candidates and lists those it left; without it intake decides every candidate, as before, and its `--dry-run` still makes no request (#1360).
- The reprioritize row's webhook hints are `milestone` `closed` and `release` `published` (`CONST_ROADMAP_REPRIORITIZE_BATCH_KEYS`); any other milestone event is no longer one (#1360).
- `ChangeKind.RELEASE_STARTED`, which nothing recorded, is removed, and `IssueRecord` carries the issue's `updated_at` (#1360).
- `RoadmapStore.add_item` returns the Item it added, `Item` and `BoardEntry` carry the card's node id (`card_id`), and `changes_since` takes `except_actor`, an empty one leaving out nothing. The run record card is written by the id `gh project item-create --format json` returns, with no board read after the create (#1361).
- The `--dry-run` request plans list each board write's card read and its `item-edit` by node ids, and the board's fields and each filter's listing once a run; intake's placement lists no board read after its add (#1361).
- `require_budget`, `require_write_floor` and `require_floor` put the budget's reset in their error's details (`reset_at`, ISO 8601), and `refusal_reset` reads it back (#1400).
- A roadmap store that has sent no GraphQL request reports no spend and sends no budget query (#1400).
  - A `devops roadmap` command whose store sent none ends with no GraphQL line.
  - The `--dry-run` plans list the closing budget read only for a run that sent a GraphQL request.
  - `RoadmapStore.graphql_spend(read=False)` reports from the budgets already held and sends nothing.
- `LocalDurabilityCapability` is built on pydantic-ai's public durable engine API: an `engine_spec` and a backend that runs each operation in-process. Toolsets are not wrapped, and model requests go through pydantic-ai's durable model in the same process. An `event_stream_handler` must be async, as pydantic-ai's `EventStreamHandler` type requires. pydantic-ai now rejects a second durability capability on the same agent (#1446).
- A `PydanticAgent` tool that takes a context must annotate it with pydantic-ai's `RunContext`. A tool annotated with `devops_cli.ai.agents.context.RunContext` now fails schema generation, because the private pydantic-ai hook that accepted the subclass no longer exists. Use `isinstance` to narrow to the subclass when the tool reads `loaded_capability_ids` or `tool_call_approved` (#1446).
- `calculate_usage_cost` prices through `genai_prices.calc_price` and returns its `PriceCalculation`, or None when genai-prices cannot price the model or usage. `get_active_traceparent` reads the active span through OpenTelemetry's W3C trace-context propagator (#1446).

### Removed
- The `devops_cli_llm_cache_hits`, `devops_cli_llm_cache_misses` and `devops_cli_llm_cache_writes` gauges (#816). Each sent 1.0 from a short-lived process and counted nothing; `devops_cli_ai_requests_total`'s `cached` label carries hits.
- `devops gh project sync --task-file`, the task-file parser (`parse_tasks_to_project_items`, `ProjectItem`) and sync's invented item counts (#878, #892).
- `DEFAULT_GH_GRAPHQL_SAFETY_THRESHOLD`; `DEFAULT_GH_GRAPHQL_BUDGET_FLOOR` is the one GraphQL threshold (#892).
- The broker's per-request `allow_private_network` override, its `allow_private_networks` argument and `HttpClientBroker.validate_url`; `ALLOW_PRIVATE_NETWORK_ENV` in `devops_cli.ai.client` and `CONST_AI_ALLOW_PRIVATE_NETWORK_ENV`; the Jaeger and probe resolve-and-check copies (`_is_unsafe_ip`, `_resolve_safe_jaeger_target`, `_resolve_safe_socket_addr`, `_is_blocked_metadata_host`). `connection_limits` moved from `devops_cli.http.pool` to `devops_cli.http.client` (#898).
- `devops_cli.ai`, `devops_cli.ai.agents`, `devops_cli.ai.agents.pydantic_agent`, `devops_cli.ai.result` and `devops_cli.ai.run` no longer re-export these pydantic-ai internals: `best_effort_price` (removed from pydantic-ai), `OutputSchema`, `OutputValidator`, `TextOutputSchema`, `run_image_process_hooks`, `run_output_with_hooks`, `SyncStreamBridge` and `current_otel_traceparent` (#1446).

### Fixed
- **Vault commands use the token `devops vault login` stores**: the broker resolves its token from the argument, then the stored login (only for the Vault address and namespace that issued it), then `VAULT_TOKEN`, then `DEVOPS_CLI_VAULT_TOKEN`, through the shared resolver, so `devops vault audit` records each lookup. `vault status` shows a Token row naming the source, or the address a stored token that was passed over was issued for, and the dry runs of `get`, `set`, `sync` and `leases` name the token source (#709).
- `vault set`, `vault sync` and every `vault leases` mode exit 1 before any request when no token is usable, naming `devops vault login`, `VAULT_TOKEN` and `DEVOPS_CLI_VAULT_TOKEN`. When Vault answers 401 or 403, commands exit 1 naming the token's source and the status, with no keyring fallback. A refused `vault leases --revoke` prints the status Vault answered (#709).
- `vault get` answers from the OS keyring only with no usable token, when Vault has no value at the path, or when Vault is unreachable, and says which source answered; the not-found message names only the sources checked. `vault sync`, `devops gh secrets sync --source vault` and the shared secret chain read Vault alone, and `vault sync` of a path with no secret exits 1 instead of reporting zero secrets (#709).
- `vault login --store` exits 1 before logging in when no encrypted, unlocked OS keyring can keep the token, instead of reporting success with the token kept only in memory, and a Vault refusal of the login is reported instead of a traceback (#709).
- **Response-cache hits are counted as cached requests (#816).** A reply the response cache answered was never recorded, so the spend ledger's cached count, `devops_cli_ai_requests_total{cached="true"}` and every review `profile.json`'s `cached_calls` stayed 0. The client now records each hit, after the cached entry passes its check, as one cached request with no tokens and no cost, in the stage of the caller: chat, the persona agent or the verifier. A cached entry the client rejects and an append-cache starting point are not hits. `devops ai spend` leaves hits out of its active and per-provider server counts and its local requests, the ledger's Prometheus exporter counts only requests sent to a model, and the AI spend dashboard gains a "Response Cache Hit Share" panel.
- `KubernetesService.read_pod_logs` returns a `PodLogStream` in both follow and non-follow modes using unpreloaded streaming (`_preload_content=False`), eliminating raw JSON representation errors and framing lines across chunk boundaries using an incremental UTF-8 decoder split strictly on newline delimiters (#864).
- `PodLogStream` enforces a bounded line length ceiling (`DEFAULT_LOG_MAX_LINE_CHARS = 65536`) only when pending text strictly exceeds the cap, ensuring lines of exact cap length with newlines in subsequent chunks frame without spurious empty lines (#864).
- `devops k8s logs` and `devops argo workflows logs` stream framed log lines directly through `write_stdout` with secrets masked and without Rich markup or terminal hard-wrapping, while mid-stream errors in non-follow mode raise immediately without duplicate fallback output (#864).
- `devops docs check` resolves every `devops` and `uv run devops` argv list under `src/devops_cli`, not only the MCP server's. It reports a computed token left over where the command takes no more arguments, so a stack handed to `deploy-stack` without `--stack` fails the check instead of failing at run time (#868).
- When Qdrant is unreachable, `devops ai rag index` and `devops ai rag index-kb` print one tip, `devops k8s deploy-stack --stack llm`, a command `deploy-stack` accepts (#868).
- `devops gh project reconcile` reads an unknown or expired GraphQL quota instead of treating it as spent and printing `Would change 0 of 0`: it starts with GraphQL's own budget query and refuses, with exit 1, only when fewer than 250 points would be left (#892).
- Reconcile plans every change on the cards already on the board before making any, so the plan and the live run match. A run stopped by the mutation budget, the GraphQL quota or a failed `item-edit` says why and how many planned changes remain, and exits 1; a failed write is no longer dropped (#892).
- A planned Status or Priority value that the board's field has no option for, such as an open pull request's In Review on a board without it, refuses `devops gh project reconcile`, `--plan` included, before any write, naming the value and the board's options; it used to fail the same write on every run (#892).
- Reconcile's and sync's help and MCP descriptions name Status and Priority only; neither ever wrote Milestone (#892).
- `run_gh` fails closed on a paginated API read when a page exits 0 but is empty, malformed JSON, contains a preamble, or has an unexpected response shape, returning exit code 1 naming the endpoint and page rather than returning a truncated listing (#1034).
- A paginated read (`run_gh` with `--paginate`) carrying `-q`/`--jq`, `-t`/`--template`, `-i`/`--include`, or `--silent` is rejected before making any request, exiting non-zero and naming the incompatible flag in stderr (#1034).
- `devops gh api graphql --paginate` is classified as a query and takes the paged path, exiting non-zero with a message stating that GraphQL queries do not support `--paginate` (#1034).
- Paginated reads inject `per_page=100` by default into page URLs when omitted, and fail closed naming the page cap when reaching `DEFAULT_GH_MAX_PAGINATED_PAGES` while still full (#1034).
- `_query_timeline_copilot_state` queries `issues/{pr_number}/timeline?per_page=100` without `--jq` and filters events in Python using `actor.login` or `user.login` (#1034).
- **Release pushes reach the person's credential helper (`devops release pr`, `devops release prepare --create-pr`, `devops release tag --push`)**:
  - The cut branch push, the release tag push and the cut's fetch of the release branch now run git with the person's whole environment, as their own `git push` does. The devcontainer's helper in `GIT_CONFIG_*`, VS Code's helper socket, the keyring's session bus and an SSH agent reach git. Before, the sanitized subprocess environment dropped them, and git failed with "could not read Username" (#1124).
  - Git still gets only the session's GitHub token (#767). It no longer asks for a username on the terminal, though an askpass program the person configured, such as VS Code's, still runs (#1124).
  - A failed push or fetch stops the command with git's reason, credentials masked and its text shown as written, so `[remote rejected]` keeps its brackets. A failed fetch of the release branch no longer lets the cut go on from a stale `origin/release/v<version>` (#1124).
  - `release tag --push` pushes the release tag alone (`refs/tags/v<version>`), not every local tag (#1124).
  - From an agent's shell, `release pr` and `release tag --push` now authenticate. Direct pushes to `release/v<version>` by `release prepare --create-pr` and the automatic cut require Write role bypass on GitHub release ruleset 23059172; ruleset refusals (GH013) raise a typed `ReleasePushRefusedError` naming the bypass requirement (#1124, #1280).
- **Automated release cutting diagnoses ruleset refusals and raises typed errors (`roadmap-service`, `devops release pr`, `devops release prepare`)**:
  - Direct pushes to `release/v<version>` refused by GitHub branch rulesets (`GH013`) raise a typed `ReleasePushRefusedError` naming the ruleset refusal and the Write role bypass requirement on ruleset 23059172 (#1280).
  - Every failure mode in `cut_release` now raises a typed `DevOpsCLIError` subclass naming its cause instead of a bare `typer.Exit(1)`: `ReleaseWorkingTreeDirtyError` for dirty working trees, `ReleaseRemoteFetchError` for remote fetch failures, `ReleaseBranchMissingError` for missing tracking refs, `ReleasePushError` / `ReleasePushRefusedError` for push failures, and `ReleasePRCreationError` for PR creation failures (#1280).
  - When `cut_release` fails during `roadmap-service` background closure jobs, the job failure record and Loki logs capture the structured exception and cause rather than an uninformative `Exit(1)` (#1280).
- A critical fix filed into the current release while its release pull request is open now joins it: `devops roadmap intake` places it there and `devops roadmap reprioritize` admits it with an "is cut, and a critical fix still joins it" comment, so the fix's pull request merges into `release/vX.Y.Z` before the release pull request does. Before, the job moved it to the next release, and a known regression shipped unless a person put the fix back by hand, as #1290 needed (#1294).
- `pytest_collection_modifyitems` adds the bubblewrap skip to `bwrap`-marked tests only where `HostSandbox().is_available()` is false, restoring execution of all 22 live bubblewrap test cases in the devcontainer (#1337).
- An item a person places in a release now stays there, and the roadmap reprioritize job comments on a rule it breaks instead of moving it out. When a person moves an item into a started release or a cut release, the item is admitted (`Action.ADMIT`) with a comment explaining the bypassed rule, and tracked with a distinct `Joined` mark so later runs do not add duplicate comments. Additionally, `devops roadmap intake` preserves candidate milestones, and release field writes verify milestone state before updating (#1349).
- The roadmap Service's `metrics` job now clones its repository, as `close` and `refine` do, and walks the release tags of that clone. It used to run `git tag` in the pod's working directory, which is not a git repository, so every run logged `Failed to inspect git tags` and `devops_cli_project_releases_total` read 0 for every repository. A clone that can't be prepared now fails the job, as it fails `close` and `refine` (#1358).
- The `metrics` and `refine` jobs fail, naming the job and `needs_clone`, when they are run without their repository's clone, instead of reading the working directory (#1358).
- `collect_project_metrics_report(root=...)` walks the tags of the repository at `root` as given, so a clone kept under `.data/` inside a workspace checkout reports its own releases, not the checkout's. Without `root`, as in `devops gh metrics`, it still uses the working tree around the current directory (#1358).
- Intake reads `.github/labels.yml` at a run's first candidate, before any timeline read, embedding call or proposal, and a run with no candidate does not read it. A missing file, or one that declares no `type/*` label other than `type/epic`, now stops intake with a configuration error that names the repository and the file and says the file must declare the `type/*` labels intake may assign; a file that is no label specs names the repository too. Any other failed read of the file is still reported as GitHub's error (#1358).
- A shipped release starts the next one without a person: the roadmap poll on GitHub now reports a GitHub Release published since the jobs last ran as a ship, and a release pull request opened, or closed unmerged, as a cut or an un-cut, read from the REST releases and pull request listings 20 entries a page, with no GraphQL request. A ship is reported whoever published it, so the Service never drops one as its own change. Before, only the in-memory store reported release changes, and a ship was seen only through the milestone webhook hint, which a restart right after the ship lost (#1360).
- The Service decides reprioritize with `reprioritize.is_due`, the rule the lifecycle machine tests, given the current release: a ship, cut or un-cut, a change to an item in the current release since reprioritize last ran, and once a day for the stall check, which the Service never ran before. A change in a planned release, or one older than reprioritize's own last success, no longer makes it due, and judging a change reads nothing from the store (#1360).
- A round runs close, reprioritize and metrics before intake and refine, and intake decides at most 5 candidates a round, never-decided or since-edited ones first, oldest first. Its record of the candidates it left (`intake.json`, beside `schedule.json`) survives a restart, makes intake due at the next poll while fresh ones remain, and is written before any placement, so intake keeps the round's skips and folds when a placement raises, and a candidate whose placement raised is decided again after the fresh ones (#1443 gives each placement its own failure); a record that can't be read fails the intake job, naming the file and the remedy. A burst of new issues no longer holds back a release's start or the metrics for an hour or more (#1360).
- The roadmap store writes a board field by the card's node id and reads only that card first, so a job-record mark costs about 3 GraphQL points instead of about 215, and filing and placing a critical fix a small constant (about 17 in the tests' fake GitHub, which leaves out the few queries gh makes to resolve an add) instead of about 1,500, whatever the board's size. It no longer sends `gh project field-list` or an `item-edit` that names a card by URL or a field by name, each of which reads the board's first 100 items with every field value, and no longer re-reads the whole board before each write (#1361).
- Intake writes to the card `gh project item-add` returns, so a placement no longer fails with "#N is not on the board after intake added it" while GitHub's board listing has not shown the new card yet (#1361).
- A store reads the board's fields once, and each filter's board listing once, for its life, one command or one Service round, and its own writes keep that listing current: a reprioritize run reads the board once instead of twice, and a Service round reads it once however many changes its triggers look up. Closing an issue drops the listing, because the board's own "Item closed" workflow then sets the card's Status, so a release cut rendered in the same round shows Done (#1361).
- A roadmap job's board write stops with `RoadmapCardChangedError` before any edit when someone changed that field after the job's store read the board, unless the card already holds the value the job writes, so a job never reverts a person's change it did not see; the job fails and the next round plans with the change (#1361).
- A Service round whose new events are all its own reads no board: the store drops them before it attaches job records (#1361).
- A board write still refuses before it starts while fewer than the 250 reserved GraphQL points are left, now read from its card read's `rateLimit` (#1361).
- `devops roadmap close` also closes the items delivered into a release whose milestone closed before closure ran. For each closed Release that still holds an open issue, it reads the pull requests merged into that release's branch first and closes the items of that release they deliver, with the usual comment. It lists the rest under the release's own heading, and none of them holds the current release's cut. An item a person reopened there stays open and is named, since a job never reverts a person's change. An item a pull request into the current release's branch closes is listed once, as a closing. Closure reads `release/vX.Y.Z`, the branch the cut makes, even for a milestone titled without its `v`. A run with no such Release reads what it read before, and the dry run lists the extra reads under their own condition (#1362).
- `chat_structured` tells the model the schema its reply must match, for intake and for both refine steps: the system message ends with the schema's JSON Schema, introduced by the `structured_output_schema.md` prompt, the `gateway` provider also sends it as `response_format` (type `json_schema`, without `strict`) and the `ollama` provider as `format`. Its first attempt validates the reply before the response cache serves or stores it, so a reply that fails the schema is never cached or replayed and still gets the reflection retry, which now names every violation with its fix hint. `StructuredOutputValidationError` counts the last reply's violations (`violations`), and its message keeps only that count and the error types, never a key the model invented (#1363).
- `devops roadmap refine` and the service's refine job skip only the item whose model call fails: the other items are refined and written, the plan lists the skipped item with its error class and schema violation count but no model text, and the run then exits 1 with `RoadmapRefineError` (`ROADMAP_REFINE_FAILED`). Rejected credentials still stop the run at the first item, and intake's refine hook still reports a failed refine (#1363).
- Refine's research and proposal prompts move to `roadmap_refine_research.md` and `roadmap_refine_proposal.md`; the proposal prompt names every `RefinementProposal` field, and the issue reaches the model as one JSON document (#1363).
- A gh call in the second or two after a quota window's reset no longer fails with "Rate limit state for subcommand 'core' is in an unknown or broken state". When GitHub's `rate_limit` answer still reports the window that has just ended, `run_gh` waits until one second past that reset and then runs the command. It logs one INFO record naming the resource, the reset in UTC, how far the clock is past it and the wait. The roadmap Service lost a round, a job or a metrics read to this error about once an hour (#1364).
- `run_gh` still fails closed with `GitHubRateLimitError`, and the command never runs, when GitHub's answer has no `remaining` and `reset` for the resource (the error names the resources it does report), or when the local clock is more than 5 s past the reset GitHub just reported (the error names both times in UTC and the gap) (#1364).
- The roadmap Service's job clone tracks the current release's `release/vX.Y.Z` while origin has that branch, and origin's default branch otherwise: between a ship and the next release's start, and while no release is open. Close and refine no longer fail with "is not a commit" while the next release has no branch. The clone fetches with `--prune`, so the branch a ship deleted no longer passes for a live one, and with no release open the clone follows the default branch instead of keeping the commit it last had. When a release is current but has no branch, the Service logs one INFO line naming the release and the default branch it checked out (#1366).
- A failed fetch, `remote set-head`, `symbolic-ref`, checkout, reset or identity write in the job clone raises `GitOperationError` naming the git command and git's reason, credentials masked. Only a release branch that `git rev-parse --verify` finds absent after a successful pruning fetch selects the default branch (#1366).
- A GraphQL budget refusal in a roadmap Service round now holds every repository's rounds until 5 s after the reset it names (#1364's clock-skew bound). Before, each worker started its next round at once against the machine account's spent budget (#1400).
  - The refusal may come from a read outside any job, such as `changes_since`, or from a failed job, whose reset `RoadmapRunError.reset_at` carries.
  - The Service logs the wait once for each new reset, and the triggers that arrive meanwhile run as one round per repository after it.
  - A drain during a pause doesn't wait for the rounds it holds, and it joins each worker it stops.
  - The rate limiter's own errors, which carry `reset_epoch` or #1364's `reported_reset` details, hold nothing. A pause time that can't be read is a warning naming its class, and the worker carries on.
- Each Service round that sent a GraphQL request ends, however it ends, with one line naming its repository, the account's GraphQL points spent during the round, and the points left (#1400).
  - A round a refusal ended takes the line from the refusing budget and makes no closing budget read, so the pause starts at once.
  - A closing read that fails, with any error, is a warning naming the error's class and never hides the round's own error.
- Intake places an open issue whose board card a person archived. Before, it failed every round with "Board #N does not hold card … that #N was just added as." and stopped the round's other placements with it. `gh project item-add` names the archived card, because the board keeps one card per issue, and the store now restores it with `gh project item-archive --undo` after one read of that card. It refuses below the GraphQL reserve and fails closed when gh answers with another card. A restored card keeps what it holds: one with a Priority gets no other write, keeps its milestone and gets no comment, and `--confirm` names it as left as it was; one without a Priority keeps its milestone and its values, and intake writes only its empty fields and a reason comment for them, so the job record never claims a value a person set (ADR 0002). `devops roadmap intake --help` says how to keep such an issue off the roadmap: close it as not planned. The in-memory store keeps the same contract, with `archive_card` for tests, and the `--dry-run` request plan lists the restore under the add, under its own condition (#1403).
- A release no longer takes the roadmap Service down. The Service image a release pins now exists before `main` pins it, so Argo CD never rolls roadmap-service onto a missing image (#1451).
  - Each push to `release/vX.Y.Z` that holds version X.Y.Z and changes the image's inputs builds, smoke-tests and scans `service:vX.Y.Z`, pushes it by digest, attests it, and only then tags it. The release pull request shows the result as the **Build & Publish Service Image** check. Right before it tags, the run checks again that its commit is the branch tip and that `main` doesn't hold the version yet, so a release merged during the build keeps the image `main` pins.
  - The check fails when `main` has image changes the release branch lacks; `main` commits that leave the image alone don't count. `RELEASE_CYCLE.md` shows how to merge `main` into the branch.
  - On `main`, `release.yml` points `latest` at that image instead of rebuilding it, once its `release.yml` provenance verifies. It never replaces a tag `main` pins: when `main`'s tree has other image inputs, it warns and the difference ships in the next release. It builds the image only when no image has the tag.
  - `ci.yml`'s **Service Image** job no longer builds the release pull request's image a second time.

### Security
- `vault status`, and the MCP `vault_status` tool whose address the client chooses, never send `X-Vault-Token`, and a stored token is sent only to the Vault that issued it (#709).
- Every Vault request, logins included, refuses a redirect to another origin, so neither the token nor a login body follows a redirect off the configured Vault address; httpx2 strips only `Authorization` on such a redirect (#709).
- `vault sync` never writes the keyring entry that holds the login token (#709).
- `devops k8s deploy-stack --stack llm` applies the LLM gateway's NetworkPolicy `llm-gateway-perimeter` before the gateway's Deployment, and `teardown-stack` deletes it. On a cluster without Argo CD the gateway used to run with no policy, so its egress was unrestricted (#795).
- The gateway's egress no longer admits every pod on ports 11434 and 8000 through an ipBlock rule for the private address ranges, nor two pod selectors that no workload carries. It admits the Ollama tiers, Valkey and DNS, plus the vLLM rule that #820 removes. A test derives the backends from the gateway's ConfigMap and Deployment, and another fails on any wider egress (#795).
- An HTTP client built by `devops_cli.http.client` checks the address it dials, at the connect and on every redirect hop, so a DNS rebinding answer can no longer slip past a check made earlier. Its connection pool is an `httpcore2` pool whose network backend resolves the host once, refuses every answer when any is unsafe for the client's egress level (public, loopback or private), and dials only the vetted addresses, as IP literals, each in turn. TLS and the Host header keep the hostname. `web_fetch` makes one lookup per hop, where it made four on the first hop and three on each redirect (#898).
- Cloud metadata addresses, as #897's classifier lists them (169.254.169.254, 169.254.170.2, `fd00:ec2::254`, `fd20:ce::254`, their integer, hex, NAT64, 6to4, Teredo and IPv4-mapped spellings, and the metadata host names), and scoped IPv6 addresses are refused at every level, by address as well as by name. That includes clients that reached any address before: the Kubernetes API-server proxy client and the cluster-service URLs (#898).
- Link-local addresses other than metadata, such as the 169.254.1.2 a rootless Podman container reaches its host at, are refused at the public and loopback levels and allowed at the private level, so the documented `host.docker.internal` setups keep working for the Kubernetes and Vault clients and the sandbox probe (#898).
- Clients built by the factory ignore `HTTP_PROXY`, `HTTPS_PROXY` and `ALL_PROXY`: a proxy would be the peer the check vets instead of the destination. `web_fetch`, `devops install-tools` downloads, the DuckDuckGo and Tavily tools, the harness documentation fetch, the GitHub and Cloudflare Statuspage fetch, Jaeger trace queries, the sandbox probe, every Vault request, and cluster-service requests stop using an environment proxy; the AI clients already did not use one. A workstation that reaches the internet only through a proxy loses those requests (#898).
- Narrower: `devops install-tools` downloads are public-only, and `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` no longer lets them reach a private address; every redirect hop must be https, where an https-to-http redirect was followed. The DuckDuckGo and Tavily tools, the harness documentation fetch and the Statuspage fetch, which checked no address, are public-only. The documentation crawler (`devops ai ingest docs`), which refuses private addresses with `allow=False`, no longer has the environment variable widen that check (#898).
- Wider: the sandbox HTTP and TCP probes run at the private level, so a target answering a link-local host-gateway address is probed where it was refused; `probe_tcp` dials each vetted address in turn instead of only the first answer (#898).
- Jaeger is queried at its configured hostname at the loopback level, as before admitting loopback and public addresses and refusing private ones whatever the flag. Its HTTPS certificate is now checked against the hostname rather than the IP address, and a URL's userinfo no longer reaches the Host header (#898).
- A native `devops k8s deploy-stack --stack infra` (or `all`) applies the `monitoring` namespace's default-deny perimeter, `monitoring-default-perimeter`, through the `monitoring` kustomization right after the root kustomization creates the namespace and before any chart installs into it. Only Argo CD applied it before, so on a cluster without Argo CD every pod could reach Prometheus, Grafana, Alloy and Pyroscope (#913). A test now fails for any NetworkPolicy under `k8s/` that deploy-stack does not apply, unless an exemption names the issue or the path that owns it.
- A sandbox workspace can no longer expose a container engine socket, the user's runtime directory or its session bus (#1115). `devops docker sandbox`, `devops test sandbox` and `devops sandbox deploy` now run one shared workspace check, and each command keeps its own error type and exit code. It refuses a workspace that is, holds or sits under any of these directories, and the refusal names the workspace and the directory:
  - `/run`, and so `/run/user/<uid>` with its session bus, gpg-agent and keyring sockets, and `/var/run` where it links to `/run`;
  - `$XDG_RUNTIME_DIR` when it is set to an absolute path, for example VS Code's `/tmp/user/<uid>`, so a workspace of `/tmp` is refused there;
  - the directory of the unix socket `DOCKER_HOST` names (default `/var/run/docker.sock`), as docker-py derives it, and, when that socket is a symlink such as Docker Desktop's WSL link, the directory it leads to. Reading the endpoint makes no connection and no request, and a `tcp://` endpoint names no socket. A `DOCKER_HOST` the client cannot parse, such as `fd://` or `tcp://host:abc`, refuses every workspace. A socket chosen through a Docker context is not followed yet (#1108).
- The workspace check no longer looks for the text `docker.sock` in the path. A directory holding `podman.sock` was let through before.
- `devops docker sandbox` and `devops test sandbox` now refuse what `devops sandbox deploy` already refused: a workspace path containing `..`, and a workspace under a system directory such as `/etc/ssl` or `/var/lib/...`.
- The MCP tools `docker_sandbox` and `sandbox_deploy` run the same check on `workspace` before they build a command line. The client gets the refusal as a tool error and no command runs.
- pydantic-ai moves from 2.35.0 to 2.54.0, with pydantic-ai-slim, pydantic-evals and pydantic-graph; the resolver also moves anthropic to 1.12.1, openai to 3.26.1 and google-genai to 2.29.0. This fixes three advisories: GHSA-4x9p-g9wm-8q7f (tool and agent run spans put content in exception events even with `include_content=False`), GHSA-fpf4-vwcp-v4hp (quadratic title extraction in `web_fetch` blocked the event loop) and GHSA-vmxc-h2x2-jmf3 (an IPv6 zone identifier got past the SSRF cloud-metadata blocklist, which devops-cli's URL pre-flight checks and connect-time egress check also use). `uv audit` passes again, and with it `uv run devops ci` and the pre-push gate (#1446).

## [0.2.28] - 2026-10-07

### Added
- Every reported scanner finding and dependency advisory is admitted with its producer's anchor (`ToolAnchor` or `AdvisoryAnchor`) and a location validated against the reviewed commit in `devops_cli.review.admission.admit()`, writing `findings.sarif` and rendering introduced, pre-existing, and suppressed findings in `review.md`, one suppressed row per file and line (only scanner findings are compared with the base revision; every dependency advisory is listed as introduced), with admission rejections counted by type in `profile.json`; an inline marker suppresses only findings of its own tool (`nosec` for Bandit, `nosemgrep` or `no-semgrep` for Semgrep, `noqa` for Ruff), and findings from the review's models are not admitted (#871, #1295, #1341).
- Increase in-cluster `roadmap-service` analysis task context window in `k8s/devops/configmap.example.yaml` from 16k (`16384`) to 64k (`65536`) tokens (#1271).

### Changed
- Unify pull request check runs and commit status contexts retrieval into a single fail-closed reader supporting combined statuses across >30 contexts and reporting zero checks as pending across `pr wait`, monitor, and readiness (#769).

### Fixed
- Defend dashboard domain panels against mounting race conditions by deferring snapshot rendering when unmounted or during child query races, preventing `NoMatches` worker failures (#519).
- Isolate MCP in-process child process stdio to temporary files to prevent protocol stream corruption, return bounded masked failure output with FastMCP `ToolError` on non-zero exit codes, and expand `ci_run` tool to accept any gate check name with budgeted timeout (#839).
- Ensure `web_fetch` reports failed HTTP fetches as tool failures (`ToolFailed`) and security blocks as errors, rather than returning failure descriptions as page text (#894).
- Align all hand-written documentation (`README.md`, `ARCHITECTURE.md`, `RELEASE_CYCLE.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/DEVCONTAINER_USAGE.md`, `docs/VISION.md`, `k8s/README.md`, and `k8s/llm/profiles/README.md`) to name only commands, options, flags, and architecture patterns that exist, backed by static argv validation in `devops docs check` (#921).
- Reviews of branches and pull requests scan an isolated detached worktree of the reviewed revision under user data root instead of the active checkout, preventing uncommitted edits from leaking into review findings or symbol metadata (#1047).
- Git change set parsing uses `git diff --name-status -M` to ensure deleted files are never passed to static analyzers, and renames track the target path at head while preserving old paths (#1047).
- Single-file path reviews resolve repository root via `git rev-parse --show-toplevel`, and uncommitted reviews report scanning in place (#1047).
- Pre-analysis of the worktree reuses cached metadata when content hash matches the commit blob, bypassing mtime checks (#1047).
- PR reviews fetch head from `refs/pull/N/head` and mark partial context when unavailable (#1047).
- Path classes loaded from `.devops/review.toml` route fixtures and golden sets to secret scanning only, skipping general analyzers (#1047).
- Detailed per-tool coverage matrix recorded in `profile.json` and rendered under `## Coverage` in `review.md` (#1047).
- Gitleaks regex fallback deleted in favor of deterministic binary execution; missing binary reports as not installed (#1047).
- Ensure a review verifier verdict that both confirms and refutes its finding stays unverified with a `verifier-contradiction` note rather than ending `VERIFIED` or `verifier-inconclusive`, even when its reason repeats the title or confirms the claim (#1059).
- A failing embedding model pauses RAG lookups with a circuit breaker after three consecutive transient errors instead of permanently ending RAG for the run, while permanent errors from unknown or unserved models stop RAG with one warning (#1065).
- Route lookups concurrently once healthy while coordinating a single probe after failures, avoiding serialized wait loops across concurrent review workers (#1065).
- Hash prompt-prefixed text for L1 and Valkey L2 embedding cache keys, supporting distinct model prompt prefixes across `qwen3-embedding`, `bge-m3`, `nomic`, and `e5` families (#1065).
- Pin `CONST_KNOWN_EMBEDDING_DIMENSIONS["qwen3-embedding"]` to 1024, honor configured `ai.rag.top_k` and `ai.rag.score_threshold` (including threshold 0), skip package manager lockfiles, and bound semantic chunks to 8,192 estimated tokens, which is 32,768 characters at the project's four-characters-per-token estimate (#1065, #1296).
- End failed indexing batches with exit 1 naming the first and last file. A run without `--force` resumes where it failed: a file is cached once all of its chunks are stored and as incomplete until then, so a file that spanned the failed batch is embedded again, and its stored chunks are purged if it is deleted or edited first (#1065, #1296).
- Route review requests through the LLM gateway with `least-busy` routing and `cancel_on_disconnect: true`, avoiding edge cut stalls and backend queue build-up on Ollama (#1069).
- `devops ai gateway connect` automatically discovers and configures the gateway's NodePort address on the LAN, probing `/health/liveliness` and `/model/info` while bypassing edge timeouts (#1069).
- Enforce single retry layer across LLM client transports: retryable status codes (408, 429, 5xx) retry with exponential backoff while non-retryable 4xx errors fail immediately without retry loops (#1069).
- Lower a gateway review's file workers from 16 to three, the sum of `DEFAULT_GATEWAY_REVIEW_SLOTS`, or to `ai.ollama_max_parallel` per `ai.ollama_urls` entry when that is more. Each file's personas still query the gateway in parallel, so requests in flight can exceed the slot count. Isolate persona retry execution, and purge expired or CLOSE-WAIT connections from the HTTP connection pool (#1069).
- Track `main` across all Argo CD git-source `targetRevision` fields under `k8s/argocd/` while retaining the release version pin for the service image in `k8s/devops/kustomization.yaml` (#1261).
- Fix Portkey AI Gateway liveness and readiness probe path to `/` and align GPU Feature Discovery image to `nvcr.io/nvidia/k8s-device-plugin:v0.16.2` (#1267).
- Disable ambient Logfire pytest plugins in test runner configuration to prevent network DNS lookups in dry-run tests (#1267).
- Resolve Argo CD application synchronization and manifest generation failures: specify valid port `number: 3100` for `loki-ingress`, deduplicate Grafana dashboard ConfigMap ownership between `base` and `monitoring`, remove redundant `Service/pyroscope` alias colliding with the Pyroscope Helm chart, and remove the homelab domain from the committed overlays; a native `deploy-stack --stack infra` applies `k8s/monitoring/dashboards` itself (#1279, #1297).
- Supply the homelab's values to Argo CD at deploy time instead of from the repository (#1290):
  - `devops k8s deploy-stack` renders ConfigMap `devops-cli-config` from `config.yaml`, outside any Application.
  - It writes the hosts each of the Applications `devops` and `ingress` renders, at the revision Argo CD builds (or `--argocd-revision`), onto the Application as Kustomize patches. The `cluster` app-of-apps ignores those patches.
  - It renders everything before it writes, and refuses an unset service setting or domain by name.
  - `teardown-stack` deletes the ConfigMap, and the repository no longer tracks `k8s/devops/configmap.yaml`.

### Security
- Redact secret-bearing argv items from async subprocess telemetry command summaries and terminate the entire POSIX process group on subprocess timeouts (#780).
- Render untrusted web pages as escaped markdown within context budget with dynamic backtick fencing, chrome/dialog decomposition, prompt boundary tag sanitization, and response URL provenance isolation (#896).

## [0.2.27] - 2026-10-06

### Added
- **Kubernetes deployment health diagnosis (`devops k8s doctor`)**:
  - Add `devops k8s doctor` command and `k8s_doctor` FastMCP tool to diagnose cluster deployment health and correlate symptoms across nodes, pods, and warning events (#408).
  - Attribute workload symptoms to cluster-level root causes, absorbing resident pods into node findings and identifying stuck PersistentVolume reclaims (#408).
  - Support `--namespace`, `--context`, `--tail`, `--format table|json|yaml`, and `--dry-run` execution with deterministic ranking and secret masking (#408).
- **Argo CD GitOps cluster state reconciliation**:
  - Introduce a two-level root Application topology (`bootstrap` tracking `main` and `cluster` tracking the active release branch) managing 20 leaf Applications (8 raw manifests and 12 multi-source Helm charts) (#755).
  - Establish `homelab` and `homelab-system` AppProjects with cluster-scoped kind whitelisting and orphaned resource tracking (#755).
  - Add declarative domain overlays under `k8s/overlays/homelab/` replacing templated overlays and standardizing ingress patching (#755).
  - Add `monitoring/grafana-admin` secret to keyring push table with live credential adoption (#755).
- **Sequential pipeline stage context budgeting**:
  - `MultiAgentPipeline` allocates carried outputs from prior stages newest-first up to `DEFAULT_PIPELINE_STAGE_CONTEXT_TOKENS` (4,096 tokens, overridable via `--stage-context-tokens` or constructor), listing older stages that get no budget by name only and appending `ScratchpadBuffer.render_context_summary()` once after carried outputs outside the budget (#859).
  - `PipelineStepResult` records `context_tokens` (exact token count of carried context sent to the stage) and `context_truncated` (#859).
- **`devops pr update --dispatch-ci` flag**:
  - Add `--dispatch-ci` to `devops pr update` to poll the head branch SHA and trigger `ci.yml` via GitHub Actions workflow dispatch after updating branches (#984).
  - Grant `actions: write` permission exclusively to `update-pull-requests` in `.github/workflows/update-prs.yml` and add architectural invariants gating Actions write permissions across all workflows (#984).
- **Pinned invariants survive memory summarization, lead every system prompt and recur on a cadence**:
  - Partition `AgentMemory` with an `invariants` store that survives extractive and LLM summarization as well as `clear()` operations (#985).
  - Prepend non-negotiable operational rules verbatim at the head of every system prompt, recur compressed reminders on a 3-turn cadence using stdlib `textwrap.shorten`, and seed `devops ai chat` sessions with `DEFAULT_CHAT_INVARIANTS` (#985).
- **OpenTelemetry tracing for background service and Kubernetes workloads**:
  - Enable OpenTelemetry export in `k8s/devops/configmap.yaml` targeting the in-cluster collector at `http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318` (#1197).
  - Add egress rule to `k8s/devops/networkpolicy.yaml` (`devops-default-perimeter`) permitting TCP ports 4318 and 4317 to namespace `otel` for all current and future workloads in namespace `devops` (#1197).
  - Configure `OTEL_SERVICE_NAME: roadmap-service` in `k8s/devops/roadmap-service/deployment.yaml` (#1197).
  - Instrument `create_service_app` with HTTP request tracing and timing middleware (skipping trace spans on `/healthz`, `/readyz`, `/metrics` probes) and trace batch job executions in `RepoWorker._execute_batch` (#1197).
- **DevOps Stack in `deploy-stack` & `stack all`**:
  - Add `"devops"` stack to `devops k8s deploy-stack` and automatically include it in `devops k8s deploy-stack --stack all`, ensuring all in-cluster manifests (`networkpolicy.yaml`, `serviceaccount.yaml`, `configmap.yaml`, `cronjob.yaml`, and `roadmap-service`) and secrets are deployed and kept up to date (#1225).
  - Pre-register namespace `devops` in `k8s/namespaces.yaml` with `restricted` pod-security standards and ArgoCD Prune=false annotations (#1225).
  - Add automated rollout restart of `deploy/roadmap-service` in namespace `devops` during stack deployment to apply updated ConfigMap values immediately (#1225).
  - Update `AGENTS.md` instructions with the architectural requirement that all in-cluster Kubernetes resources must have a managed stack path in `deploy-stack --stack all` (#1225).
- **GitHub Traffic Metrics & Automated Telemetry Ingestion in Roadmap Service**:
  - Add GitHub repository traffic and engagement telemetry instruments (`devops_cli_project_traffic_views_total`, `devops_cli_project_traffic_views_uniques_total`, `devops_cli_project_traffic_clones_total`, `devops_cli_project_traffic_clones_uniques_total`, `devops_cli_project_traffic_referrers_total`, `devops_cli_project_traffic_paths_total`, `devops_cli_project_stars_total`, and `devops_cli_project_forks_total`) (#1227).
  - Implement `record_project_metrics_in_registry` to populate in-memory metrics registry for direct Prometheus scraping via `roadmap-service:8000/metrics` (#1227).
  - Add scheduled `metrics` job to `DEFAULT_DUE_TABLE` in `roadmap-service` running immediately on startup and every 15 minutes to continuously refresh repository velocity and traffic metrics (#1227).
  - Add GitHub Traffic & Repository Engagement section with stat and bargauge panels to the `Project & Engineering Velocity` Grafana dashboard (`k8s/monitoring/dashboards/project-metrics.json`) (#1227).
  - Add traffic and referral summaries to `devops gh metrics` CLI output (#1227).
- **Dynamic DevOps ConfigMap Generation & Sanitized Template**:
  - Add `k8s/devops/configmap.example.yaml` template with sanitized placeholder repositories and account name (#1231).
  - Add `/k8s/devops/configmap.yaml` to `.gitignore` and untrack it from version control to prevent user repos and bot accounts from leaking (#1231).
  - Add `devops_cli.k8s.configmap` module with `ensure_devops_configmap` and `render_devops_configmap_content` to dynamically materialize and synchronize the cluster ConfigMap from active configuration (`service.repos`, `service.machine_account`, or `k8s.github_account`) (#1231).
  - Update `devops k8s deploy-stack` and `devops k8s render` to ensure `configmap.yaml` is generated from active settings before applying manifests (#1231).
- **GitHub & Cloudflare Published Service Status Monitoring**:
  - Add `devops gh status`, `devops cloudflare service-status`, and unified `devops status` commands to monitor published upstream platform operational status, active incidents, and component health (#1235).
  - Add Statuspage domain models (`StatuspageSummary`, `StatuspageComponent`, `StatuspageStatus`, `StatuspageIncident`) and telemetry client in `devops_cli.telemetry.service_status` (#1235).
  - Register `devops_cli_upstream_service_status` and `devops_cli_upstream_component_status` OpenTelemetry/Prometheus instruments, recorded continuously by the metrics adapter in `devops roadmap run` (#1235).
  - Integrate published service status into Grafana dashboards: stat panel on `ingress-tunnel.json` (Cloudflare Service Status) and dedicated row with GitHub and Cloudflare status panels on `project-metrics.json` (#1235).
- **Keep issues with open or merged pull requests in active releases**:
  - Update roadmap store pull request queries (`open_pull_requests`) to index both `OPEN` and `MERGED` states via GitHub GraphQL and in-memory store (#1244).
  - Add `Event.PR_JOINED` and `Reason.PULL_REQUEST` transitions so items with in-flight or merged pull requests joining a started or cut release are admitted and kept rather than demoted to the backlog (#1244).
  - Guard release start and descoping rules so items with pull requests remain in the starting release even if `New` or `Blocked`, and are excluded from over-cap descoping victims (#1244).

### Changed
- **Stack lifecycle and release management delegation**:
  - Update `devops k8s deploy-stack` to detect Argo CD-managed clusters, run secret push, and delegate manifest and Helm reconciliation to GitOps (#755).
  - Guard `devops k8s teardown-stack` against manual execution when Argo CD manages the cluster (#755).
  - Pin Helm release versions across all stack manifests and CLI upgrade commands (#755).
  - Automate Argo CD git `targetRevision` rewriting to the next open roadmap release during `release prepare` and `release cut` (#755).
  - Enforce `Prune=false,Delete=false` sync options across all namespaces and persistent volume claims (#755).
- **Instruction surfaces and agent documentation**:
  - Remove hardcoded gate counts across documentation surfaces, aligning with unified gated quality gate terminology (#840).
  - Rescope automatic Copilot review statements to PRs into `main` only, noting monthly token budget rationale (#840).
  - Update issue template references in `AGENTS.md` to supported templates (`bug_report.yml`, `feature_request.yml`) (#840).
  - Add `--force` flag to `devops ai agents`, refusing to overwrite existing `AGENTS.md` without `--force` while writing pointer stubs and exiting non-zero (#840).
  - Remove vestigial `_pointer_stub` helper from `devops_cli.commands.ai` (#840).
  - Add offline test suite `tests/test_agents_md_claims.py` verifying issue template existence, persona enum consistency, and pointer stub byte equality (#840).
- **Required CI checks bind merges into release and main**:
  - Remove deprecated `.github/branch-protection.yml` and clarify help text across `devops gh branch-protection` commands to indicate management of classic branch protection rather than rulesets (#842).
  - Author ADR 0004 recording the CI verification policy, required check names (`Static Analysis` and `Tests & Coverage`), strict mode, `update-prs.yml` dispatch route, and owner decisions on Copilot reviews (#842).
  - Add glossary definitions for `Gate`, `Check`, and `Required check` to `CONTEXT.md` (#842).
- **Dependency updates from closed Dependabot pull requests**:
  - Bump `fastapi` from 0.141.1 to 0.142.2 (#1201).
  - Bump `gitpython` from 3.1.62 to 3.2.0 (#1202).
  - Bump `genai-prices` from 0.1.6 to 0.1.9 (#1200).
- **Transition from Dependabot to Renovate (`.github/renovate.json`)**:
  - Replaced `.github/dependabot.yml` with `.github/renovate.json` for GitHub Actions and Docker dependency tracking (#1219).
  - Disabled automated Python package updates in Renovate to manage `uv` dependencies deliberately as part of project workflow with synchronized `uv.lock`.
- **Devops Kubernetes services route to qwen3.8:27b on ollama-48gib-slow**:
  - Update `devops-background` in `k8s/llm/gateway/configmap.yaml` to serve `ollama_chat/qwen3.8:27b` on `http://ollama-48gib-slow.llm.svc.cluster.local:11434` (#1221).
  - Configure `k8s/devops/configmap.yaml` (`devops-cli-config`) to route default `model`, `tasks.analysis.model`, and `tasks.chat.model` to `devops-background` on the background tier (#1221).
  - Synchronize gateway routing catalog in `src/devops_cli/k8s/gpu_matrix.py`, workload profiles comments in `k8s/llm/profiles/ollama-profiles.yaml`, documentation in `k8s/README.md`, and Ollama knowledge base (#1221).
- **GPU Configuration Matrix & Service Aliases Asset Extraction**:
  - Extract static dictionaries (`profiles`, `provider_service_aliases`, `speed_tier_service_aliases`, and `gateway_routes`) from `src/devops_cli/k8s/gpu_matrix.py` into structured JSON asset `src/devops_cli/k8s/gpu_matrix.json` (#1223).
  - Eliminate obsolete and vestigial `vllm` references from hardware profiles, service aliases, and CLI filtering options (#1223).
  - Streamline `src/devops_cli/k8s/gpu_matrix.py` from 845 lines to under 130 lines by loading the JSON asset via cached parser, eliminating iterative dynamic attribute loops (#1223).
- **Agent instructions for continuous roadmap-service, concurrency guardrails, and health checks**:
  - Documented in-cluster `roadmap-service` architecture, continuous daemon execution (`devops serve --service`), webhook handling, and autonomous batch jobs (#1236).
  - Established strict concurrency guardrails prohibiting overlapping manual roadmap mutations (`devops roadmap close --confirm`, `devops roadmap intake --confirm`) while `roadmap-service` is active (#1236).
  - Provided comprehensive verification and liveness diagnostic procedures (`kubectl` deployment/pod status, HTTP `/readyz` and `/healthz` probes, logs, metrics), credential rotation recovery, and safe offline manual fallback protocols (#1236).

### Removed
- **Automated PR synchronization workflow (`update-prs.yml`)**:
  - Removed `.github/workflows/update-prs.yml`, eliminating automated base-branch merges into open pull requests on push events and associated Actions approvals and duplicate CI runs (#1217).

### Fixed
- **PR monitor fail-closed Copilot review state handling**:
  - `devops pr monitor` reports Copilot review state as `unread` with `unread_reason` when timeline or review reads fail, rather than reporting `completed` or `idle` (#806).
  - Treat `unread` Copilot state as not review-ready and keep polling until settle/timeout, reporting the unread reason upon timeout rather than certifying ready (#806).
  - Include unread Copilot review diagnostics in `failure_reasons` and JSON/YAML structured output (#806).
- **CI quality gate execution cache tree certification**:
  - The CI execution cache verifies whole-tree state against deterministic Git and blob fingerprints, removing the legacy file-subset caching path and `--files` CLI parameter (#838).
  - Compute workspace fingerprint before quality gates execute for full, non-dry runs, certifying after checks pass that the tree did not mutate during the run before saving cache (#838).
  - Emit a warning and record nothing in the CI cache if the working tree changed during gate execution, preserving existing cache and exiting with the passing verdict (#838).
  - Treat file arguments or `--files` flags passed to `devops ci` as Click usage errors with exit code 2 and 0 gate executions (#838).
- **CLI startup imports no telemetry when disabled**:
  - Set `PYDANTIC_DISABLE_PLUGINS=logfire-plugin` unconditionally at module level before importing `devops_cli` modules, ensuring the Logfire pydantic plugin is disabled across all CLI invocations (#858).
  - Deleted `logfire.instrument_pydantic()` and decoupled `devops_cli.exceptions` from AI domain exceptions, preventing `pydantic_ai`, `logfire`, and `opentelemetry.sdk` from loading on top-level and subcommand `--help` invocations (#858).
  - Re-derived timing ceiling test assertions in tree-sitter, context packer, inspection, and fastmcp suites as runaway bounds ($\ge 20\times$ baseline and $\ge 1\text{ s}$) (#858).
  - Eliminated duplicated coverage step duration in CI pipeline gate summaries and consolidated pytest worker configurations into a single `pyproject.toml` setting (#858).
- **`skip_rag` parameter propagation in multi-agent pipeline**:
  - Forward `skip_rag` from `MultiAgentPipeline.run` to `agent.run(...)` and pass `skip_rag=not rag` in `devops ai pipeline` command (#859).
- **Streamed interactive chat turn history and memory rollback**:
  - `_stream_interactive_chat_turn` appends the user prompt to `agent.memory` before invoking `client.chat_messages_stream`, ensuring the model receives both prompt and prior conversation history (#874).
  - Pop trailing user entries from `agent.memory` before falling back to `agent.run` during thinking-only stream turns, and when streamed turns fail or are interrupted with `KeyboardInterrupt`, leaving agent memory as it was (#874).
- **CI quality gate and subcommand execution under dry-run**:
  - `devops ci` checks, runners, and subcommands start zero subprocesses and mutate no external state when `--dry-run` is active (#885).
  - Return dry-run `CheckResult`s carrying `dry_run=True` and render ordered `PlannedRequest` execution plans via `render_request_plan` for single checks and aggregate runs (#885).
  - Bypass coverage artifact cleanup and prevent saving or clearing gate cache under dry run (#885).
  - Add planned index run preview to `devops ci coverage --build-index --dry-run` without writing cache files or hashing source trees (#885).
- **Egress guards refuse cloud metadata in every numeric, NAT64, and provider form**:
  - Replaced ad-hoc string prefix checks (`startswith("169.254.")`) and partial lists with `pydantic_ai._ssrf` network classifiers and `dnspython` syntax parsing (#897).
  - Enforced refusal of IPv4 link-local, IPv6 link-local (`fe80::/10`), NAT64 metadata (`64:ff9b::169.254.169.254`), 6to4, Teredo, dword/hex/octal representations, fullwidth dot encodings, and provider internal metadata hostnames (`metadata.google.internal`, `metadata.goog`, AWS/Azure/GCP metadata endpoints) across all egress paths (#897).
  - Refactored `is_loopback_host` and `is_cloud_metadata_host` to deterministically parse and classify addresses without brittle subset heuristics (#897).
- **Knowledge base commands, options, and component references accuracy**:
  - Add static Markdown command argv collector and integrate into `devops docs check` to ensure all command lines and options in knowledge base articles resolve statically (#920).
  - Synchronize all Python package versions with `pyproject.toml`, remove phantom settings and environment variables (`DEVOPS_CLI_CONFIG_PATH`, `DEVOPS_CLI_LOG_LEVEL`), update default embedding models, and replace legacy numbered gate terminology with unified Gated standards across all 80 bundled knowledge base articles (#920).
- **Dependabot target branch and taxonomy labels (`.github/dependabot.yml`, `.github/labels.yml`)**:
  - Target Dependabot to `main` across `github-actions`, `pip`, and `docker` ecosystems without hardcoding release version branches (#1189).
  - Apply standard taxonomy labels (`type/chore` with `scope/ci`, `scope/cli`, and `scope/infra`) to Dependabot configurations and register missing scopes in `labels.yml` to satisfy `devops gh labels audit` (#1189).
- **Service image build provenance subject name in `release.yml`**:
  - Add explicit `subject-name: ghcr.io/${{ github.repository }}/service` to the `Attest Build Provenance` step in `.github/workflows/release.yml`, satisfying the requirement of `actions/attest-build-provenance@v2` when `subject-digest` is provided (#1192).
- **Domain Templating in `deploy-stack` & Roadmap-Service Ingress**:
  - Automatically substitute domain placeholders in Kubernetes manifests during `devops k8s deploy-stack` using `resolve_template_domain()`, preventing redeployments from reverting ingress hostnames to `example.com` (#1229).
  - Add `--domain / -d` support to `devops k8s deploy-stack`, aligning it with `apply` and `render` (#1229).
  - Update `k8s/devops/roadmap-service/ingress.yaml` to use `pathType: Prefix` on `/webhooks/github` for robust webhook routing (#1229).
  - Register `roadmap-service` Ingress route in `k8s/ingress/ingress-routes.yaml` for complete coverage under Cloudflare Wildcard Tunnel integration (#1229).
- **Grafana Dashboard "Value" Ghost Series**:
  - Filter `{api_base!=""}` on Litellm gateway panels in `k8s/monitoring/dashboards/llm-stack.json` to prevent unrouted metric samples (`{}`) from displaying as `"Value"` in legends (#1235).
  - Fix legend format placeholders from `{{ node }}` to `{{ instance }}` in CPU and Memory utilization panels in `k8s/monitoring/dashboards/k8s-views-global.json` (#1235).
- **DevOps CLI Telemetry dashboard command variable covers all registered subcommands**:
  - Update `$command` template variable in `k8s/monitoring/dashboards/devops-cli.json` (`devops-cli-telemetry`) to a custom variable pre-populated with all 39 registered devops subcommands (#1241).
  - Prevent subcommands with zero recent Prometheus invocations from being missing from the dropdown filter and repeating subcommand latency breakdown panels (#1241).
  - Add test coverage in `tests/test_grafana_dashboards.py` verifying that every registered CLI subcommand is covered by the dashboard's template variable options and query (#1241).
- **Discriminate Kubernetes manifests for Kube-linter and Pluto review scans**:
  - Filter candidate files in review static scanner pipeline via `_is_scannable_manifest` and `_scan_kubernetes_manifests`, preventing missing/deleted files from triggering scanner `lstat` failures (#1242).
  - Implement `is_kubernetes_manifest` check verifying `apiVersion` header presence and schema document structure, ensuring generic non-manifest YAML files (workflows, label taxonomies, dependabot configs) are bypassed by Kube-linter and Pluto (#1242).
- **Security audit fix**:
  - Upgrade `multidict` from 6.8.0 to 6.9.1 in `uv.lock` resolving vulnerability GHSA-54p9-h82j-f925 (#1242).
- **Scope roadmap reprioritization pull request queries to avoid full repository enumeration**:
  - Update `_OPEN_PULL_REQUESTS_QUERY` and `_OpenPullRequestsPayload` to query `openPrs` (`states: [OPEN]`) and `recentPrs` (`states: [MERGED]`, newest first) within a single GraphQL query, preventing single-page `_require_whole` truncation exceptions against repository-wide historical pull requests (#1246).
  - Retain backwards-compatible `AliasChoices` for `pullRequests` payload mapping in unit test doubles (#1246).
- **Classify project metrics and upstream status snapshot instruments as gauges**:
  - Add `InstrumentKind.GAUGE` to `src/devops_cli/telemetry/instruments.py` and route gauge emissions to `tracer.record_gauge(...)` (#1253).
  - Reclassify point-in-time inventory instruments (`PROJECT_ITEMS_TOTAL`, `PROJECT_COMMITS_TOTAL`, `PROJECT_PRS_TOTAL`, `PROJECT_CI_RUNS_TOTAL`, `PROJECT_RELEASES_TOTAL`, `PROJECT_STARS_TOTAL`, `PROJECT_FORKS_TOTAL`, `PROJECT_TRAFFIC_*`, `UPSTREAM_SERVICE_STATUS`, `UPSTREAM_COMPONENT_STATUS`) from `COUNTER` to `GAUGE`, preventing the OpenTelemetry Collector's `deltatocumulative` processor from monotonically accumulating point-in-time snapshots into vastly inflated metrics on Grafana dashboard `project-metrics.json` (#1253).
  - Update Panel 5 in `k8s/monitoring/dashboards/project-metrics.json` to compute interval per release by dividing release interval sum by count (#1253).
  - Update `docs/TELEMETRY.md` and add test coverage in `tests/test_telemetry_instruments.py` for gauge metric recording (#1253).

### Security
- **Collaborator trigger guard and expression isolation in `update-prs.yml`**:
  - Restrict the `issue_comment` trigger in `.github/workflows/update-prs.yml` to repository collaborators (`OWNER`, `MEMBER`, `COLLABORATOR`), ensuring unauthorized PR comments produce a skipped job without consuming Actions runner minutes (#754).
  - Move GitHub Actions expressions (`${{ ... }}`) out of `run:` script bodies into step `env:` variables to eliminate shell injection attack surfaces (#754).

## [0.2.26] - 2026-10-04

### Added
- **Coverage Reverse Index Test Selection (`devops ci coverage --build-index`, `devops ci test`)**:
  - Added `--build-index` option to `devops ci coverage` to generate a per-worktree reverse coverage index (`coverage_index.json`) mapping source files to covering test files using `COVERAGE_CORE=ctrace` and `--cov-context=test` (#406).
  - Enhanced `devops ci test` to select tests deterministically from the reverse coverage index, automatically incorporating working-copy drift since index creation and falling back to text-based selection on missing sources (#406).
  - Added atomic persistence and pre-/post-run working-tree mutation verification during index generation, aborting and cleaning up when repository files change during the run (#406).
  - Enforced full test suite escalation when trigger files (`conftest.py`, `pyproject.toml`, `uv.lock`, `.python-version`) change, with `--no-fallback` rejection support (#406).
- **Ruff Correctness Rule Families (`B`, `RUF`, `ASYNC`)**:
  - Extended Ruff lint selection to whole rule families `B` (flake8-bugbear), `RUF` (Ruff-specific rules), and `ASYNC` (flake8-async), catching runtime bugs, mutable defaults, and unhandled exception chains (#420).
  - Selected targeted single rules: `SIM115` (unclosed file handles), `PT011`, `PT015`, and `PT017` (pytest assertion and raises integrity), and `PGH003` (explicit type ignore codes) (#420).
  - Configured `allowed-confusables` for typographic mathematical and informational glyphs (`–`, `×`, `ℹ`) and enabled `ignore-without-code` in mypy configuration (#420).
  - Resolved all 146 rule violations across the codebase, added architectural invariant tests for suppression rules and mypy configuration, and lowered the C901 suppression ceiling from 66 to 65 (#420).
- **devops-cli in the cluster (`k8s/devops/`, `devops k8s run-job`)**:
  - Namespace `devops` with a suspended CronJob template, a token-less service account and a default-deny perimeter; cluster jobs reach the gateway directly (#741).
  - `devops k8s run-job -- ARGS` creates a Job from the template with only its args changed, follows its log and exits with its exit code; `--dry-run` reads nothing, not even the CronJob, and prints the kubectl requests a run would make (#741).
- **Cluster Secrets from the keyring (`devops k8s push-secrets`)**:
  - One table lists every Secret the stacks read; the command adopts live values, generates the ones nobody types and needs `--rotate` to replace a live value (#741).
  - Server-side apply from stdin: values never reach argv, files, annotations or output (#741).
  - `--dry-run` makes no request, reads included, and prints the requests a push would make in order with placeholders; `--plan` reads the keyring, the cluster and, for the machine account, gh's own record of it, says so, and prints each key's state (#741).
  - The machine account's token comes from gh's keyring through `gh auth` alone: gh must list the login with a keyring token its own check passes, and devops-cli never calls GitHub with that token, so a run keeps one GitHub identity (#741).
- **Hidden prompt for credentials (`devops config set KEY`)**:
  - Omitting VALUE for a credential prompts for it, keeping it out of shell history (#741).
- **Single-Entry Item Intake (`devops roadmap intake`, FastMCP `roadmap_intake`)**:
  - Open issues off the board, unfinished items and new `--title`/`--body-file` candidates get a duplicate check, a code-checked type, Priority, Value and Effort, and a placement; P0 needs verified evidence from a trusted source (#742).
  - Agent candidates are labelled `source/agent` and open, borrow (`budget/borrowed`) or fold under the agent filing quota (#1153), with its numbers on every run (#742).
  - The dry-run rule (#412): `--dry-run` makes no request, to GitHub, a model or the telemetry collector, and prints the requests a run makes in order with placeholders, as an `IntakePlan` marked as a dry run, each request a `PlannedRequest` (#741) that shows the exact `gh` command where it is known without a read, the condition it runs on and whether it repeats per page or per candidate; `--plan`, which intake without a mode flag runs, reads GitHub and calls the model, writes nothing and reports its spend (GitHub requests by REST, REST search and GraphQL, embedding and proposal calls); `--confirm` writes. The FastMCP tool takes `mode` (`plan` by default, `dry-run` or `confirm`), and a FastMCP tool dispatched in-process with `--dry-run` exports no telemetry either (#742).
  - Agent instructions file new work through intake, and `devops gh issues triage` reports issues off the board as awaiting intake instead of missing a milestone (#742).
- **`devops roadmap close`**: closes as completed each open issue that a pull request merged into the current release's branch closes, with one comment saying what changed (the pull request, its merge commit, the first section of its body and its changed-file count) and how it was verified (each check run with its bucket, and the Acceptance Criteria of the issue's task file at the merge commit). A pull request whose check runs can't be read closes nothing, and the run exits non-zero. Once the release holds no open item, at least one item closed as completed and no release pull request, it writes `docs/ROADMAP.md` on `chore/cut-vX.Y.Z` in the clone at `--root` and opens the release pull request into the default branch, ready for review, through the shared cut path; completed items with no changelog fragment are listed. Writes only with `--confirm`; `--plan` previews, `--dry-run` makes no request. MCP mirror `roadmap_close` previews only (#743).
- The roadmap store reads every pull request merged into a branch, with its merge and head commits and changed paths, from both adapters (#743).
- **`devops roadmap refine`**: item refinement to Ready with proposed design, tasks, and acceptance criteria. Selects New items from the next planned release by priority, then New backlog items up to the release cap. Gathers minimal repository context (`CONTEXT.md`, ADRs, cited files, grep identifiers) and up to 3 Tavily search queries for public repositories. Uses structured model output (`RefinementProposal`) validated deterministically against repository commits, cited lines, and verified sources. Writes sanitized plain-text markdown between markers `<!-- devops-roadmap-refine:start -->` and `<!-- devops-roadmap-refine:end -->` on the issue body with SHA/branch tracking and 65k size limit guard. Items that fit in one pull request with complete criteria and no open questions move to Ready with reason comments; oversized items remain New with `refine.needs_split="true"` and are descoped by reprioritization. Supports `--dry-run` and `--confirm`. Hooks into `apply_intake` for critical fixes and P0 features. Added FastMCP mirror tool `roadmap_refine` and due table integration in `devops roadmap run` (#744).
- **Continuous Service Mode for `devops serve`**:
  - Added dedicated continuous service mode (`devops serve --service`) for in-cluster deployment, processing and authenticating GitHub webhooks with per-repo single-concurrency job dispatch and coalesced batches (#752).
  - Added `ServiceConfig` to configuration settings (`repos`, `machine_account`, `poll_interval_seconds`, `drain_timeout_seconds`) and managed credential `service.webhook_secrets` (`DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS`) for repo-to-secret HMAC mapping (#752).
  - Added structured single-line JSON log formatter (`JsonLogFormatter`) emitting timestamp, level, logger, message, and contextual metadata with zero credential, payload, or signature leakage (#752).
  - Implemented `POST /webhooks/github` route with 25 MiB size enforcement, Content-Type verification, constant-time HMAC-SHA256 signature verification, 10,000-delivery LRU deduplication, ping handling, and machine-account suppression (#752).
  - Added `/healthz`, `/readyz`, and `/metrics` Prometheus endpoints recording delivery outcomes, trigger sources, job counts, job durations, start timestamps, and queue depth (#752).
- **Production Service Image for Scheduled Jobs and Webhook Handlers (`Dockerfile`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`)**:
  - Root `Dockerfile` multi-stage build packaging Python 3.14 runtime, `gh` CLI, `git`, and `devops-cli` virtual environment into a hardened, non-root (`1000:1000`), read-only container with `/etc/gitconfig` credentials (#753).
  - Pinned base images (`python:3.14-slim-trixie`, `ghcr.io/astral-sh/uv`) by SHA256 digest with BuildKit layer caching and minimal attack surface (#753).
  - CI workflow `service-image` job validating content change detection, build/load smoke testing under full sandbox constraints (`--read-only`, `--tmpfs`, `--cap-drop ALL`, `no-new-privileges`), and Trivy vulnerability auditing (#753).
  - Release workflow `service-image` job publishing `ghcr.io/dan-petty/devops-cli/service:v<version>` and `:latest` with SPDX SBOM generation and cryptographic build provenance attestation via GitHub Actions (#753).
  - Dependabot `docker` ecosystem tracking in `.github/dependabot.yml` and release routine verification instructions in `docs/ROUTINE_TASKS.md` (#753).
- **`devops roadmap run`**: evaluates the roadmap due table across landed jobs (`intake`, `close`, `reprioritize`) in a fixed execution order, tracking each job's last successful run time per repository in `<data dir>/roadmap/<owner>/<name>/schedule.json`. Clones repositories for jobs requiring code checkouts to `<data dir>/roadmap/<owner>/<name>/clone`, synced to the tip of `origin/release/vX.Y.Z` with session identity. Supports `--dry-run` and `--confirm` modes. Wires `service_job` adapter to `devops serve --service` for processing coalesced trigger batches. Adds FastMCP mirror tool `roadmap_run` reporting due jobs (#981).
- **Roadmap Service Kubernetes Deployment**:
  - Added single-replica `Recreate` Deployment for `roadmap-service` in the `devops` namespace running `serve --service --host 0.0.0.0 --port 8000 --workers 1` with restricted security context, `devops-cli` Secret environment, and health probes (#1083).
  - Added dedicated 1Gi `local-path` PersistentVolumeClaim (`roadmap-service-home`) mounted at `/home/devops` with Argo CD prune/delete protection (#1083).
  - Added ClusterIP Service and Traefik Ingress routing external traffic strictly to `POST /webhooks/github` (#1083).
  - Added `roadmap-service-ingress` NetworkPolicy admitting incoming connections on TCP 8000 only from Traefik in `kube-system` and Prometheus scraping in `monitoring` (#1083).
  - Added Prometheus egress rule in `k8s/monitoring/networkpolicy.yaml` allowing TCP 8000 metrics scraping into namespace `devops` (#1083).
  - Registered `DEVOPS_CLI_SERVICE_WEBHOOK_SECRETS` in the cluster secrets push table with `deployment/roadmap-service` rollout restart targeting (#1083).
  - Updated `devops-cli-config` ConfigMap with `service.repos` and `service.machine_account` (#1083).
- Runtime dependency `graphql-core==3.3.0` (#1125).
- `devops roadmap reprioritize`, `migrate` and `render --plan`: a read-only preview that ends with the GraphQL points spent and left; `migrate` and `reprioritize` without a mode flag still preview, and `render` without one writes the file (#1125).
- **Agent Filing Quota Specification & Pure Quota Engine (`devops_cli.roadmap.quota`, `.github/roadmap.toml`, `.github/labels.yml`)**:
  - Six roadmap quota configuration keys (`open_issue_limit`, `throttle_start_fraction`, `overage_step_fraction`, `release_credit_base`, `release_credit_per_delivered_item`, `release_item_target`) with Pydantic field constraints and declared repository defaults in `.github/roadmap.toml` (#1153).
  - Pure calculation module `src/devops_cli/roadmap/quota.py` exposing exact arithmetic implementations of `ratio(n, config)`, `release_credit(delivered, config)`, and `allowance(n, delivered, closures, config)` (#1153).
  - Added declarative repository labels `source/agent` and `budget/borrowed` in `.github/labels.yml` (#1153).
  - Established agent filing quota, borrowing, and consolidation guardrails in `AGENTS.md` and `src/devops_cli/ai/instruction_generator.py` (#1153).
- **Grafana Observability Enhancements (`k8s/monitoring/dashboards/`)**:
  - Added 30-day, 90-day, and 1-year AI spend run rate projection stat panels to `ai-spend.json` (#1158).
  - Added rolling average trend lines (`rate(...)[6h]` and `rate(...)[30m]`) across AI spend timeseries panels (#1158).
  - Added subcommand template variable (`$command`) and per-subcommand repeating latency timeseries panels to `devops-cli.json` (#1158).
  - Added GPU memory percentage utilization timeseries panel with 90% and 95% threshold alert lines to `llm-stack.json` (#1158).
  - Added ingress traffic breakdown by host/router panel to `ingress-tunnel.json` (#1158).
  - Enabled router and service Prometheus metrics labels in Traefik ingress configuration (`k8s/ingress/traefik-values.yaml`) (#1158).

### Changed
- **Logging Namespace Pod Security Standards**:
  - Dropped `logging` namespace Pod Security Standards enforcement level from `privileged` to `baseline` in `k8s/namespaces.yaml`, as Loki and Loki canary require no hostPath mounts or elevated capabilities (#548).
  - Updated Kubernetes stack documentation in `k8s/README.md` to document the single-shipper architecture where Alloy ships container logs to Loki (#548).
- **deploy-stack pushes Secrets first (`devops k8s deploy-stack`)**:
  - Pushes the stacks' Secrets after the namespaces and before any manifest or release; `--no-push-secrets` skips it, and `--dry-run` lists key names (#741).
  - A locked keyring stops it before it applies anything; the devcontainer auto-deploy passes `--stack` and its failure warning names the unlock (#741).
- **A dry run exports no telemetry (`--dry-run`)**:
  - A command's own `--dry-run` no longer sends its spans and metrics to the telemetry collector, so a dry run makes no external request (#741).
- **Service image tag follows the release (`devops release prepare`, `devops release check`)**:
  - The bump pins `k8s/devops/kustomization.yaml` to `v<version>`, and the check fails when they differ (#741).
- **One GitHub session per process (`devops_cli.github.session`)**:
  - gh and git act only as the token `gh auth token` gives; `gh auth` sees the environment unchanged (#767).
  - Each identity keeps its own quota ledger and response cache (#767).
  - Removed `github.token`, `DEVOPS_CLI_GITHUB_TOKEN` and the unused GraphQL client: run `gh auth login`, then `keyring del devops-cli github_token` and revoke that token (#767).
- **Hermetic CI Runner & Bubblewrap Test Confinement (`.github/workflows/ci.yml`, `pyproject.toml`, `tests/conftest.py`)**:
  - Removed runner package installations (`sudo apt-get update`, `bubblewrap`, `python-is-python3`, and `sysctl` unprivileged user namespace relaxation) from `.github/workflows/ci.yml` (#832).
  - Registered `bwrap` pytest marker in `pyproject.toml` and introduced `pytest_collection_modifyitems` hook in `tests/conftest.py` to skip bubblewrap-dependent live tests when `bubblewrap` is not installed on the host (#832).
  - Made sandbox namespace refusal test hermetic using an executable stub binary in `tests/test_host_sandbox.py` (#832).
  - Added architectural invariant test in `tests/test_architectural_invariants.py` ensuring GitHub Actions workflows never mutate the runner and that `.devcontainer/Dockerfile` installs bubblewrap (#832).
- **Unified CI Quality Gate & Workflow Parity (`src/devops_cli/commands/ci.py`, `.github/workflows/ci.yml`, `tests/test_ci.py`)**:
  - Unified all CI verification gates into a single ordered `CheckSpec` table in `src/devops_cli/commands/ci.py`, ensuring CLI subcommands and aggregate gates execute identical check and fix commands (#843).
  - Added `--only` and `--skip` selection options to `devops ci` with mutual exclusivity and invalid name rejection, and ensured single-row execution streams output directly without buffering (#843).
  - Aligned `.github/workflows/ci.yml` jobs (`static`, `test`, `dependency-freshness`) to execute through `devops ci`, eliminating drift between local quality gates and remote GitHub Actions CI (#843).
  - Standardized Bandit security scanning on `-ll` across all scanners, removing global `-s B608` skips, applying targeted `# nosec B608` annotations to `instruction_generator.py` and `stack_lifecycle.py`, and removing obsolete `build_bandit_cmd` (#843).
  - Removed redundant `--xml` flag from `devops ci coverage` as `.data/coverage.xml` is written by default (#843).
  - Added offline workflow-to-table parity verification in `tests/test_ci.py` asserting all gate checks run through `devops ci` (#843).
- **Fail-closed release path (`devops release prepare`, `devops release pr`)**:
  - One shared, fail-closed release cut path (`cut_release`) creates `chore/cut-v<version>` from `origin/release/v<version>`, updates `pyproject.toml`, `src/devops_cli/__init__.py`, `uv.lock`, and the in-cluster service image tag on the cut branch, pushes with `--force-with-lease`, and opens the release pull request into `main` (#982).
  - Validates working tree cleanliness before any branch or file is touched, refusing dirty state with exit code 1 (#982).
  - Version for `devops release pr` is resolved from `pyproject.toml` on the checked-out cut branch rather than the caller's pre-checkout directory (#982).
  - Release PR opening fails closed immediately upon push errors or rejected labels/milestones, removing warn-and-continue fallback logic (#982).
  - Grounding exemption is restricted to `chore/cut-vX.Y.Z` into the default branch; PRs targeting release branches or forked cuts are held to full grounding (#982).
- The `roadmap_render`, `roadmap_migrate` and `roadmap_reprioritize` MCP tools take `mode` instead of `dry_run`, as `roadmap_intake` does: `plan` by default, `dry-run` makes no request, `write` (render) and `confirm` (reprioritize) write (#1125).
- **Grafana Visualization & AI Spend Reference Model**:
  - Resized Pyroscope continuous profiling CPU and memory allocation flamegraphs to full 100% width (`w: 24`) and stacked vertically in `sre-service.json` (#1158).
  - Restyled local savings by backend server in `ai-spend.json` as smooth individual lines with 20% semi-transparent fill (#1158).
  - Aligned default local AI equivalent reference model `DEFAULT_AI_REFERENCE_MODEL` from `gpt-4o` to `gpt-4o-mini` across defaults, pricing models, CLI commands, and example configuration to match commercial equivalents for `qwen3.8:27b` (#1158).

### Removed
- **Fluent Bit Logging Agent and Ingress**:
  - Removed Fluent Bit from the Kubernetes logging stack, manifests, and CLI stack lifecycle in favor of Alloy in `infra`, eliminating duplicate log scraping, unlabelled log streams, and unauthenticated ingress (#548).
  - Deleted `k8s/logging/fluent-bit-values.yaml` and `fluent-bit-ingress` in `k8s/ingress/ingress-routes.yaml` (#548).
  - Removed Kubernetes API server egress rule (TCP 443, 6443, 10250) from `k8s/logging/networkpolicy.yaml`, restricting `logging` egress strictly to intra-namespace and CoreDNS (#548).
  - One-time manual post-merge cleanup commands:
    ```bash
    helm uninstall fluent-bit -n logging --kube-context <cluster-context> --wait
    kubectl --context <cluster-context> delete ingress fluent-bit-ingress -n logging
    kubectl --context <cluster-context> label --dry-run=server --overwrite ns logging pod-security.kubernetes.io/enforce=baseline
    uv run devops k8s deploy-stack --stack logging --context <cluster-context>
    kubectl --context <cluster-context> get pods -n logging
    kubectl --context <cluster-context> get ns logging --show-labels
    kubectl --context <cluster-context> get networkpolicy logging-default-perimeter -n logging -o jsonpath='{.spec.egress[*].ports[*].port}'
    ```
- **Hand-made Secret steps (`k8s/README.md`, `k8s/cloudflared/secret.example.yaml`)**:
  - The `--from-literal` instructions and deploy-stack's client-side Qdrant Secret, which leaked the key into an annotation, are gone (#741).
  - `sync-secrets` no longer copies the Qdrant key into the keyring (#741).
- `devops gh issues close-merged` and the closure sweep in `github/issue_closure.py`, replaced by `devops roadmap close` (#743).
- **Dead Webhook Infrastructure**:
  - Removed obsolete `WebhookEventDispatcher`, `WebhookEvent`, `GitHubWebhookVerificationError`, and deleted legacy `graphql.py` and its tests in favor of canonical service mode webhook router (#752).
- **Removed options and fallback helpers (`devops release pr`)**:
  - Removed `--push/--no-push` option from `devops release pr` (#982).
  - Removed `_build_pr_fallback_cmd`, `_strip_pr_cmd_flag`, and `_checkout_release_branch` (#982).

### Fixed
- **Network Reference Extraction Grounded in URLs and IP Literals**:
  - Replaced heuristic bare-word and domain string inspection with strict URL parsing (`urllib.parse.urlsplit`) across any scheme and IP literal parsing (`ipaddress`), ensuring bare words, hostnames, and arbitrary identifiers are never extracted as network references (#431).
  - Eliminated heuristic constants (`CONST_BRANCH_PREFIXES`, `CONST_CODE_CONFIG_PREFIXES`, `CONST_COMMON_PROPERTY_SUFFIXES`, `CONST_TELEMETRY_CALL_NAMES`, `CONST_STANDARD_RECEIVER_IDENTIFIERS`, `CONST_EXCLUDED_FILE_MIME_TYPES`) and removed dead extraction routines, visitors, and shims (#431).
  - Simplified Python AST literal extraction to inspect all string constants directly for URLs and IPs, including in dictionary keys and function call arguments, without relying on telemetry or identifier blacklists (#431).
  - Renamed package repository asset filtering to host-only `is_trusted_registry_host(host: str) -> bool` based strictly on `CONST_EXCLUDED_PUBLIC_REGISTRIES` (#431).
  - Consolidated network reference types strictly to `"url"` and `"ip"`, removing all legacy `"domain"` reference categorization across models, extractors, and table formatters (#431).
- **GitHub write pacing decided from the request gh sends (`devops_cli.github.request_classifier`)**:
  - `run_gh` gives GitHub's one-second write interval to GraphQL mutations (`gh api graphql` with the document in `-f`/`-F query=`, an `@file`, stdin or an `--input` body, `operationName` included) and to `gh api` calls gh sends as an implicit POST (any field or `--input`), so `pr threads resolve-all`, project view and roadmap field writes, and the REST pull request fallback are paced (#1125).
  - `gh api`'s argv is read with `argparse` in every form gh accepts (`-XPOST`, `-X=POST`, `--method=post`, attached fields), and GraphQL documents with graphql-core, loaded only for a `graphql` request. A request that can't be read counts as a write (#1125).
  - High-level gh commands are classified by the verb in the verb position: a read verb (`view`, `list`, `status`, `checks`, `diff`, `show`, `item-list`, `field-list`) or the `search` group reads, any other verb writes. `gh project link` is now a write and `gh issue list --label sync` a read (#1125).
  - High-level commands find the verb past `-R`/`--repo` and `--owner`, so `gh -R o/r issue list` and `gh project --owner o item-list 2` are reads (#1125).
  - The write interval holds across resources within a process: a REST write and a GraphQL write acquired together are scheduled at least the interval apart. Only the write moves; reads keep their quota's pace and never wait behind another resource's write or quota reset (#1125).
  - A `gh api` write with `--paginate` goes to gh once, as given, paced as a write, instead of page by page as a read with `?page=1` added to its endpoint (#1125).
  - A `gh api` call is cached only when gh sends it as a GET with no field or body: a method in any form (`-X=POST`, `-XHEAD`), an attached field (`-ftitle=x`, `--field=k=v`) or an `--input` body, which the old token check let through, is no longer cached, so a repeated write is sent; reads cache as before (#1125).
  - A high-level gh command is cached only when the verb in the verb position reads: a read verb elsewhere in argv (`pr create --title list`) made the write cacheable (#1125).
  - Roadmap board reads go through the store's own paged GraphQL query instead of `gh project item-list`, which fetched every field of every item and reported no cost (a `reprioritize --dry-run` spent 2,025 of the 5,000 hourly points on 2026-10-04 while the limiter counted one call). Each page asks for `rateLimit`, and `run_gh` charges the points a GraphQL response reports. Project sync (`devops gh project sync`) reads its board with the same paged query (#1125).
  - Every board read passes a Projects filter at the source and leaves archived items out (`items(query:, archivedStates: [NOT_ARCHIVED])`); the backlog and candidate reads pass `is:open`. The read is checked against the total for the same filter, so an archived item no longer stops migrate with "Read 930 of 931", and a count that changes during the read is read again once before the run fails (#1125).
  - Before a board read, the run reads GraphQL's own `rateLimit` and the filter's total, and stops with a clear message, spending nothing on pages, when the read would leave less than 250 points; a read stops before any page while fewer than 250 are left (#1125).
  - `devops roadmap migrate`, `render`, `reprioritize` and `intake` end with one line giving the GraphQL points the run spent and the points left, read from GraphQL itself (#1125).
  - `devops roadmap reprioritize`, `migrate` and `render` `--dry-run` make no request at all: they read neither GitHub nor the roadmap configuration (a `reprioritize --dry-run` spent 2,025 GraphQL points on 2026-10-04). Each returns its real result type marked as a dry run and prints the requests a run makes, in order, each with its exact `gh` command and stdin, built by the store's own argument builders, with `<placeholders>` for values a read gives (#412, #1125).
  - `devops roadmap intake --dry-run` shows the exact `gh` command of every store request, a board write's reads included (#1125).
- **Grafana Dashboard Projections, Rolling Averages, and Panel Layouts**:
  - Consolidated multi-series rolling average queries in `ai-spend.json` into unified aggregate totals (`Total Rolling Avg`) across all servers and models, eliminating per-item rolling average line sprawl (#1175).
  - Updated AI spend and savings projections in `ai-spend.json` to calculate rates over the observed dashboard interval (`[$__range]`) extrapolated to 30-day, 90-day, and 1-year windows, replacing the fixed 1-hour active rate (#1175).
  - Fixed empty Time to First Token p95 panel in `llm-stack.json` by querying `litellm_llm_api_time_to_first_token_metric_bucket` grouped by model, eliminating failed joins on volatile LiteLLM deployment identifiers (#1175).
  - Restored Node Exporter Full dropdown selectors and system metrics by setting `useIntegrationAllowList: true` and adding `node_uname_info`, `node_load.*`, `node_disk_io_now`, and `node_netstat_Tcp_CurrEstab` to `includeMetrics` in `k8s-monitoring-values.yaml` (#1175).
  - Provisioned local `nvidia-dcgm.json` dashboard with bottom panels (GPU SM Clocks, GPU Utilization, Tensor Core Utilization, GPU Framebuffer Memory Used) organized into a balanced 2x2 grid, replacing upstream dashboard 12239's 50% single-column layout (#1175).
  - Corrected project velocity panels in `project-metrics.json` to evaluate cumulative release, milestone, and CI run counters directly as snapshot states rather than `increase()` deltas (#1175).
  - Added service traffic fallback to Traffic by Ingress Host / Router in `ingress-tunnel.json` (#1175).

## [0.2.25] - 2026-10-03

### Added
- **Model-in-the-Loop Prompt Benchmarking (`devops review corpus score`, `devops ai runs compare`)**:
  - `devops review corpus score --runs N` scores the latest N reviews of a corpus as one arm, and `--session` is repeatable. The score counts the runs that found and reported each injection, gives pass@k and pass^k, and gives the mean of each figure beside its `[min, max]` across the runs. It refuses sessions that ran different prompts, `--runs` beyond the reviews that exist, and `--session` beside `--runs`. The report says `not model-pinned` when a gateway group the review used serves more than one model (#413).
  - Each review's `profile.json` records `prompt_digest`, a digest of every prompt under `ai/tasks/` and `ai/personas/`, and corpus scores record it in their setup with the run count and the personas that replied. A corpus score also counts the findings the review raised, the verifier invalidated and verification kept (#413).
  - `devops ai runs compare` shows each run's range beside its mean when either run has one, and whether the ranges overlap (`overlaps`, `apart`, or `—` for a run without a range) (#413).
- **Per-Model Gateway Groups for the Review Pool (`k8s/llm/gateway/configmap.yaml`)**:
  - `qwen3-coder:30b` and `gpt-oss:20b`, the two models `devops-review` serves, each have a gateway group of their own. Each group copies its model's `devops-review` deployments (model, backend and weight, in order) with no `max_input_tokens` and no fallback, so a review pinned to one model is routed as the pool routes that model. `devops-review` and its weights are unchanged (#475).
- **Review Verification Task Environment Overrides (`devops_cli.config`)**:
  - `DEVOPS_CLI_AI_TASK_VERIFICATION_PROVIDER`, `DEVOPS_CLI_AI_TASK_VERIFICATION_MODEL`, `DEVOPS_CLI_AI_TASK_VERIFICATION_REASONING_EFFORT` and `DEVOPS_CLI_AI_TASK_VERIFICATION_OLLAMA_URLS` set `ai.tasks.verification.*`, as the analysis task's variables set `ai.tasks.analysis.*`. They override a verification model set in a config file, so one shell pins a review's analysis and verification to one gateway group (#475).
- **Benchmarks Without Static Scanners (`devops review benchmark --no-static-scan`)**:
  - `--no-static-scan` runs every review of the benchmark without the static scanners, so a scanner hit on an injected defect does not count as the model's recall. The run's setup records `static_scan`, so every benchmark setup now differs from earlier runs' in that key (#475).
- **Alertmanager, With a Webhook Receiver That Waits for Its Secret (`k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/grafana-values.yaml`)**:
  - The prometheus chart's Alertmanager is enabled, and Prometheus finds it through the chart's pod discovery. Since #734 removed kube-prometheus-stack, the stack had no Alertmanager and no alert rules, and Grafana had no Alertmanager datasource (#549).
  - Alerts without a routed severity go to the `null` receiver, which sends nowhere. `critical` and `warning` alerts go to `webhook`, which reads its URL from the `url` key of the Secret `alertmanager-webhook` in `monitoring` (`url_file`). The Secret is mounted optional, as a directory, so Alertmanager starts without it and picks up the file without a restart once it is created; until then each webhook notification fails and nothing leaves the cluster (#549).
  - A Not Ready node inhibits its targets' `TargetDown`, and a rule's critical alert inhibits its own warning (#549).
  - Grafana provisions the `Alertmanager` datasource (`uid: alertmanager`), so its Alerting pages list the alerts and silences (#549).
- **Alert Rules for the Homelab Nodes, GPUs, Storage and the Monitoring Stack Itself (`k8s/monitoring/prometheus-values.yaml`, `k8s/logging/loki-values.yaml`)**:
  - 23 rules in four groups: a node not Ready, a scrape target down, a node rebooted (uptime under 30 minutes, so a node that stayed down for hours still counts), no active `k3s` or `k3s-agent` unit, `nvidia-power-limit` not active, GPU temperature over 85 °C and at 90 °C, total GPU power over a 1000 W site budget, host filesystems under 10% and 5% free, kubelet-reported volumes under 10% free (no volume on this cluster reports them yet), Prometheus data over 80% of its claim, and Prometheus, Loki and Alertmanager health (#549).
  - No rule watches the controller manager, scheduler or proxy, which k3s runs inside its server process and nothing scrapes, so the false `KubeControllerManagerDown`, `KubeSchedulerDown` and `KubeProxyDown` of kube-prometheus-stack do not return (#549).
  - Retention is watched: `PrometheusSizeLimitCutHistory` fires when a size cap deletes blocks before the 30 days kept by time, and `LokiRetentionNotRunning` fires when Loki's compactor has not applied retention for over an hour. Loki's retention comes on with #550's Loki migration, whose Loki upgrade also starts the Loki scrape, so that alert has no series before the migration and afterwards fires only if the compactor stops applying retention (#549).
  - `PrometheusStorageNearClaim` reads this server's own TSDB series (`job="prometheus"`) and the largest claim size, so a second Prometheus or kube-state-metrics, as scraped for hours on 2026-10-01/02, does not stop it from evaluating (#549).
  - The Prometheus server's kubernetes-pods job scrapes Loki and Alertmanager through their pod annotations (`singleBinary.podAnnotations` in `k8s/logging/loki-values.yaml`), for their health rules. The Loki scrape exists only where the logging stack runs, so an infra-only cluster has no Loki target to report down (#549).
  - #550's `log-and-metric-retention` rules, `LogOrMetricVolumeDiskLow` and `PrometheusNearRetentionSizeCap`, route through the same receiver, and `PrometheusNearRetentionSizeCap` reads this server's own TSDB series (`job="prometheus"`) like `PrometheusStorageNearClaim` (#549).
  - `tests/test_k8s_monitoring_alerting.py` pins the rule set and checks that every expression selects only series a scrape in `k8s/` serves (#549).
- **Alerting Documented in `k8s/README.md`**:
  - The rules with their thresholds and waits, the receiver and its Secret, and planned maintenance: a `node="<node>"` silence, with `amtool` in the Alertmanager pod or Grafana's Silences page, then `kubectl drain`, so the single Alloy metrics pod moves off the node and `ClusterMetricsMissing`, which has no `node` label, does not page (#549).
  - The rule table lists every rule once, #550's two volume rules included, and says where the storage rules overlap; retention itself stays in #550's Log and Metric Retention section, which now says its alerts route through Alertmanager (#549).
- **An Alert Before the Log or Metric Volume Fills (`k8s/monitoring/prometheus-values.yaml`)**:
  - `LogOrMetricVolumeDiskLow` fires when the root filesystem of the node holding Loki's `storage-loki-0` or Prometheus's `prometheus-server` claim has had less than 10% free for 30 minutes. local-path does not hold a volume to its claimed size, so a volume fills when its node's filesystem does. The rule follows each claim through its pod to the node, so it moves with the volume (#550).
  - `PrometheusNearRetentionSizeCap` fires when the TSDB has used over 80% of `server.retentionSize` for an hour, before the cap would delete blocks younger than 30 days (#550).
  - Prometheus evaluates both and Grafana's alert list shows them. No Alertmanager is deployed yet, so they notify no one (#550).
- **Log and Metric Retention Is Written Down (`k8s/README.md`)**:
  - A new section says how long Loki and Prometheus keep data, what deletes it, each volume's size, why Loki's volume cannot simply be resized, and what the two alerts watch (#550).
- **Ruff Enforces the Complexity Cap of 10 (`pyproject.toml`, `uv run devops ci`, the `ruff-check` pre-commit hook)**:
  - `pyproject.toml` selects `C901` and sets `[tool.ruff.lint.mccabe] max-complexity = 10`, so a function over the cap (standard McCabe) fails `ruff check` in `devops ci`, in the `ruff-check` pre-commit hook and in GitHub CI. `AGENTS.md` called the cap strictly enforced, but nothing checked it: `C901` was not selected, and the `structural-invariants` hook only printed a note (#586).
  - The 66 functions over the cap when it was turned on, 65 in `src/` and 1 in `tests/`, carry a `# noqa: C901` marker. `ruff check --select C901 --add-noqa` wrote the markers in one run, and no function was decomposed in this change. `RUF100` reports a marker once its function is back under the cap, and the default `devops ci --fix` removes it. `PGH004` bans the blanket `noqa` that would hide `C901` without naming it (#586).
  - With `RUF100` selected, nine `noqa` codes that did nothing are gone. Five name rules the project does not select: `S310` three times in `ai/gateway_bench.py`, `S603` in `ai/gateway_tune.py` and `S102` in `tests/test_ai_gateway_tune.py`. Four sit where Ruff raises nothing: `F401` twice in `tests/test_exceptions.py`, and `N802` in `tests/test_sandbox_metrics.py` and `tests/test_sandbox_probe.py`. The `# nosec` comments that Bandit reads stay, and the reason "the script under test" stays as a plain comment (#586).
  - `test_c901_suppressions_stay_under_the_ceiling` counts the `C901` markers in `src/` and `tests/`, in every spelling Ruff honours, including a form feed or a no-break space where a space would go. It fails when the count exceeds `DEFAULT_C901_SUPPRESSION_CEILING` (66), names the files that carry markers, and says to decompose the function rather than raise the ceiling. A change that removes markers lowers the ceiling in the same change (#586).
  - `test_the_complexity_cap_has_no_escape` fails when `[tool.ruff]` or `[tool.ruff.lint]` holds a key outside its allowlist. The allowlists keep out Ruff's deprecated top-level `per-file-ignores` and `extend-ignore`, as well as `include`, `extend`, `extend-exclude` and `lint.exclude` (#586).
  - The same test fails when `exclude` is not `["repos"]`, when `C901`, `RUF100` or `PGH004` is not enforced or a per-file ignore waives it, or when `max-complexity` is not 10. A rule counts as enforced only when `select` names it by its own code, because Ruff reads `C9` as `C90`, so `C90` selected with `C9` ignored turns `C901` off (#586).
  - It also fails when a file under `src/` or `tests/` has a file-level exemption, when a `ruff.toml`, `.ruff.toml` or `pyproject.toml` sits under those directories, or when a `ruff.toml` or `.ruff.toml` sits beside `pyproject.toml` (#586).
  - It fails when a file under `src/` or `tests/` carries one of Ruff's own suppression comments naming `C901`: a `# ruff: ignore[C901]`, a `# ruff: disable[C901]` that holds until its `enable` or the end of the file, or a `# ruff: file-ignore[C901]`. One such comment hides any number of functions and leaves no marker to count, so these comments are banned rather than counted (#586).
  - It fails when an `.ignore` or `.gitignore` sits under `src/` or `tests/`, when an `.ignore` sits beside `pyproject.toml`, or when the project's `.gitignore` matches a source file there. Ruff skips the files an ignore file lists. Ignore files outside the checkout differ per machine and never reach GitHub CI's clean checkout. No test runs a Ruff process (#586).
- **GenAI Span Attributes Checked Against Pinned Semantic Conventions (`devops telemetry semconv refresh`, `devops_cli.telemetry.semconv`)**:
  - `src/devops_cli/telemetry/semconv_genai.json` pins the OpenTelemetry GenAI semantic conventions (`open-telemetry/semantic-conventions-genai`, which has no tagged release) to commit `b31e9e8ea26ac1c086d3313d474e31d7c3f391ae`, resolved with weaver 0.26.1, as their current attribute keys, metric names and span types (#588).
  - A gate test fails, naming `file:line`, on any quoted string starting with `gen_ai.` in `src/devops_cli/`, comments and docstrings included, that is not a current attribute key or metric name, and on any f-string that builds one (#588).
  - `devops telemetry semconv refresh --commit <sha>` resolves the conventions at a commit with `weaver registry package --v2` and rewrites the snapshot. It writes nothing and exits 1 when weaver is not on PATH, the commit is not a full SHA, or weaver fails or times out. A person runs it; the gate never does (#588).
- **Branch and PR Reviews Compute Their Own Symbol Delta (`devops review branch`, `devops review pr`)**:
  - Each review records the symbols that every changed Python file added, removed and kept since the commit its diff starts at, so an earlier `devops ai analyze branch` run is no longer needed. That commit is the merge base for a branch, `HEAD` for uncommitted changes, and the merge base from GitHub's compare endpoint for a pull request, not the base branch's tip. A branch's files are read at its own commit, so reviewing a branch that is not checked out, or one with uncommitted deletions, does not count the checkout's removals as the branch's. A renamed file is compared with its old path, an added file's symbols are all added, and a file whose base or head cannot be read gets no delta (#593).
  - Verification exempts a finding only when it cites a symbol this review's diff removed, and moves it to the file's diff hunk without asking the model. The summary's Symbol Delta row and `removed_symbol_findings_count` count only the reviewed files (#593).
- **Every Model Reply Carries the Reason It Ended (`devops_cli.ai.client`, `devops_cli.ai.direct`)**:
  - `LLMResponse.finish_reason` holds pydantic-ai's `FinishReason` (`stop`, `length`, `content_filter`, `tool_call` or `error`), read from the OpenAI-compatible `finish_reason`, Anthropic's `stop_reason` and Ollama's `done_reason` through three tables in `config/constants.py`. `max_tokens` and `model_context_window_exceeded` become `length`. An absent or unmapped value is `None`, meaning unknown, so truncation is never guessed. `to_model_response` passes the reason on and `from_model_response` reads it (#599).
  - `ai.llm.dispatch` and `ai.llm.stream` set `gen_ai.response.finish_reasons` to the provider's reason, and leave it out when the reason is unknown (#599).
- **The Spend Ledger and Review Profiles Count Why Replies Ended (`devops_cli.ai.spend`, `devops review`)**:
  - The spend ledger gains a `finish_reason` column. A ledger created before it gains the column in place and keeps its rows. Chat dispatches, streams and the pydantic-ai direct calls record the reason, and observers registered with `observe_llm_calls` receive it with each call (#599).
  - Each stage in a review's `profile.json` counts its replies by reason (`finish_reasons`, with `unknown` when the provider gave none) and the replies cut at their token cap by serving backend (`truncated`). When any reply hit the cap, the profile's summary line says how many (#599).
- **Review Sessions Record Their Subject, and History Counts Each Subject Once (`devops review`)**:
  - Every session's findings.json and candidates.json record its subject: the target type and ref, and a digest of the review pages. Both findings.json writers record it, and the persona-loop writer now stamps `generated_at` in UTC, as the pipeline does (#607).
  - One reader (`ai/review/history.py`) lists the completed sessions in a reviews directory and counts one session per subject: the one with the most human verdicts, then the most findings with a verdict, then the newest. A machine re-run or a `--no-verification` run never displaces verdicts a person wrote. Sessions written before this change each count on their own, as target-only or unkeyed. The reader parses only the fields the figures read, so it takes a fraction of a second where a full parse took seconds (#607).
- **Readiness Requires a PR to Close One Issue and Change Its Task File (`devops pr check-readiness`)**:
  - Every PR except the release PR (`release/vX.Y.Z` from the same repository into the default branch) is blocked unless its body closes exactly one issue, read as `devops gh issues close-merged` reads it, and it adds, modifies or renames that issue's `docs/agent/tasks/task-<issue>-*.md`. Each missing piece is one blocker that names it. A repository whose base has no `docs/agent/tasks/` is not checked (#704).
  - The changed files come from `pulls/{n}/files?per_page=100`, paged to the end. Where the check applies, a failed read is a blocker that names the failure; elsewhere it is a warning. The read replaces `gh pr diff --name-only`, which returned an empty list on any failure (#704).
- **GitHub-Sourced Roadmap: One-Time Migration and Generated View (`devops roadmap migrate`, `devops roadmap render`)**:
  - `devops roadmap migrate` makes GitHub the roadmap's source of truth (ADR 0001). It brings the board in line with `.github/project-template.json`: it moves the cards of options the template replaces, deletes fields the template lacks, and lists the option renames, additions and removals a person makes in the board's field settings, because GitHub's API can't keep an option's id. `--confirm` refuses before any write until the renames and additions are made. It fills unset Status and Priority from `status/*` and `priority/*` labels, closes release epics as not planned and takes them off the board, moves the open items of milestones beyond the planning horizon to the backlog and deletes those milestones, fills unset Value and Effort from the `docs/ROADMAP.md` matrix, and records each rejected or not-building idea as an issue closed as not planned. It edits no issue body and never overwrites a set field. It prints the plan and a four-section report (P0 feature candidates, entries without an issue, entries whose issue is closed, planned writes) and writes only with `--confirm`; a second run plans nothing (#739).
  - `devops roadmap render` writes `docs/ROADMAP.md` from GitHub: the current release, the planned releases within the horizon, then the backlog by priority, one line per item with its Status, Priority, Value and Effort. Two runs on the same state write the same bytes, and a failed read writes nothing (#739).
  - `.github/roadmap.toml` names the board and the roadmap jobs' settings (`release_cap`, `discovery_threshold`, `planning_horizon`, `stall_days`), and rejects unknown keys. Both commands read it, the board template and `docs/ROADMAP.md` through the contents API at `--ref` (#739).
  - MCP tools `roadmap_render` and `roadmap_migrate`, which only previews, in a new lazy `roadmap` domain (#739).
  - The roadmap store gains board creation from the template, field deletion, card listing, writes and removal, issue creation and closing with a reason and comment, Release deletion, workflow listing and repository file reads, in both adapters (#739).
  - `docs/VISION.md` holds the design principles and the themes from `docs/ROADMAP.md`, without release numbers (#739).
- **The Current Release's Admission, Cap, Descoping and Stall Rules (`devops roadmap reprioritize`)**:
  - `devops roadmap reprioritize` holds the current release, the open milestone with the lowest version, to its rules, and starts each release. After a release starts, only a critical fix (a P0 `type/bug` or `type/security` item) joins it: any other item added moves to the backlog, and a P0 feature to the next planned release. A fix that takes the release over its cap of 12 descopes the lowest-ranked unstarted item that is not a fix, and while the release holds more than the larger of its cap and its size at start, its lowest-ranked unstarted items leave too, so an item moved back to Ready after a fix filled the release makes room. An unstarted item that is Blocked, has an open blocked-by link outside the release, carries the `needs-split` label or is the last one not done is descoped to the next planned release, and an admitted critical fix only when it is Blocked. An In Progress item with no status change, pull request update or commit for 14 days goes back to Ready and is descoped (a critical fix stays), and an idle In Review item gets one nudge per window. While the release pull request is open, draft or not, and once it has merged until GitHub Release vX.Y.Z is published, the release is cut and a critical fix goes to the next release (#740).
  - When the release pull request has merged and GitHub Release vX.Y.Z is published, the job closes the milestone if it is still open, creates `release/vX.Y.Z` for the next release at the default branch's head when it is missing, sends its New items to the backlog and its Blocked items out, fills it to 12 from Ready items no person placed (critical fixes, then P0 features, then Priority, Value and number) or trims it to 12 into the planned release after it, and creates planned milestones up to the planning horizon. A release a person cut and shipped before any run started it, with its milestone still open, as while a run that would have stopped and waited, is skipped too: the run starts the first release after the shipped ones, or a first run records it, and closes every shipped milestone last, the current one first, where it used to start the shipped release, pull backlog items into it and close only the one before it. A start, or a first run at a ship, that stops at its last writes, the closes of the shipped milestones, has made every other: the next run holds the release it started or recorded to the rules and closes the milestones last, so an item a person added in between is judged then, not left until a later run is due; once that release has shipped too, its milestone closed by `release.yml` or not, the next run starts the one after it. A release a person cut before any run started it starts with nothing pulled in: nothing joins a cut release. A milestone closed without its release shipping starts nothing, and the plan says so. A backlog item a person put there stays out, even one no job ever placed, whose issue's events the start reads, and one the job had sent there before a person placed it elsewhere and back: each gets a `Left` mark naming where a person took it out of (#740).
  - The board's run record card (`Roadmap run record`) keeps the release the job last started, or recorded at its first run, and its size then, so a cleared admitted mark or an empty release never makes the job start a release again. The job names a release by its milestone number in the run record and in an item's marks, so a release renamed after it started is not started again and keeps its admitted items, while the plan and the comments use its new title. The first run records the admitted set of the release under way and moves nothing, the same release whether or not `release.yml` closed a shipped milestone; it and each start admit the release's closed items too, so one reopened there stays, and a closed item that leaves the release loses its mark like an open one, so one a person puts back and reopens is judged as a join. With the run record card gone while items carry the job's marks, the job refuses to run and names the card instead of recording a new baseline; with the card there but its `Started` mark not a milestone number, as an older version or a hand edit leaves it, the job refuses with its own message, which gives the number to set. A milestone older than the started release, such as a hotfix milestone, is held to no rule (#740).
  - Each change to an item is recorded as pending before its writes, and its reason comment is posted once, so a run that stops part-way is finished by the next one, which first judges the change again: a placement or status a person set since stands, and a change the rules no longer make, such as a fix's admission after the release was cut, is put back and decided anew. GitHub takes a field write as two calls, the job record and then the milestone or the board field, so the pending mark records each field as begun in the job-record write, before the field call, and as written in a job-record write once that call returns, and the next run counts a field as the job's only when the job wrote it and it has not changed since: the written mark keeps the field's event count or Status clock as the job's write left it, so a person who sets a field to the change's value after a dropped change put it back keeps it. For a field only begun it reads the issue's Release events or the Status's last change: a field call that never landed is made again, or its record taken back, so no `Left` mark names a release the item never reached and a release start still pulls in the item it began to; a field that holds the change's value may be the job's call that landed and reported a failure, or a person's edit, which no read tells apart, so the change is finished with its comment, and that value is never put back, written or recorded as the job's: the job record keeps no value for that field, so when the job moves an item it had placed itself, such as one a release start pulled in or a descope sent on, the next run never reads the job's own move as a person taking the item out of that place and gives it no `Left` mark, and the move clears a `Left` mark the item carried, as a confirmed move does. The job never puts back a value a person set, even the one the change was going to write, and never overwrites a person who set a field back to what it held before; the job record of a begun field a person set since is dropped, not put back to what it held before the change, so a person who moves an item back to where a job last placed it, after a stopped release start's milestone call had pulled it in, keeps it there, and the rerun's start does not pull it in again. When the issue's events show the item never joined the stopped change's target, its milestone call never landed, so that record is put back instead: an item a person moved out of the backlog and back while the rerun waited is still where the job placed it, and the start pulls it in. A change stopped before it began its Status write leaves the item's Status clock as it is, so a person who set an idle item In Progress again, or moved it into review and back, before the rerun of its stall descope keeps it in the release; and such a Status counts as the person's whatever it holds, so the rerun never writes Ready over it: a descope whose milestone call landed with nothing to show the job made it is finished with the person's Status left as it is, and one about a release that has shipped since gives way to the person's edit. A start judges an item an interrupted run moved into it like any other, and drops an interrupted pull-in whose milestone call never landed before its release shipped, so the item is judged by the start of the release after it rather than moved into the shipped one. A critical fix that joins while the stall rule readies or nudges it is admitted by that change, so a run that stops part-way through it never announces the fix's admission twice, nor sends it to the backlog after the stall comment said it stays; and a move out of the release that a person undid before its comment was posted leaves the item admitted, even when the run that posts the comment stops before its last write. The job refuses a board #739's migrate has not finished, one whose Status field lacks New or Blocked or still has Todo or Backlog, or that still holds an open release epic, naming `devops roadmap migrate` (#740).
  - Every rule reads one transition table (`TRANSITIONS` in `devops_cli.roadmap.reprioritize`). Each item the job moves, readies, admits or nudges gets a one-line reason comment; it never sets Priority, Value or Effort. It writes GitHub state only with `--confirm`; `--dry-run` lists each change with its reason. The MCP tool `roadmap_reprioritize` previews unless it is called with `dry_run=False`, and `is_due(changes, now, last_stall_check)` says when a change since the last poll makes the job due (#740).
- **Store Reads and Writes for the Release Rules (`devops_cli.roadmap`)**:
  - Both roadmap store adapters read blocked-by links, an issue's comments and its joins and leaves of releases, when an Item's Status last changed, open pull requests with their last update and last commit, a release's pull requests, whether its GitHub Release is published, the default branch and any branch, and create a branch, comment on an issue, keep a job's own marks (`Admitted`, `Left`, `Nudged`, `Pending`) in an Item's job record, also in the write that records a field's value (`set_field(..., marks=...)`), set or drop the value the job record holds for a field without setting it (`set_marks(..., recorded=..., forgotten=...)`), and keep the run record. Changes read from the issue events now carry the Item's Release and job record as they are when read. In the in-memory adapter a renamed milestone's issues and pull requests show its new title, as on GitHub, and a person can reopen an issue (#740).
- **`needs-split` Label (`.github/labels.yml`)**:
  - A person applies it to an item too big for one pull request, and reprioritization descopes the item until it is split (#740).
- **One Roadmap Store for Releases, Items and Board Fields (`devops_cli.roadmap`)**:
  - `RoadmapStore` reads and writes Releases, Items, Candidates, board fields and issue-event changes behind one interface, with a GitHub adapter over `gh` and an in-memory adapter for tests. Reads page through every result and raise rather than return an empty or partial result. Each Item write also records the value the store set in the board's `Job record` field (ADR 0002), so a later job can tell a person's change from its own (#768).
- **Why a Finding Has No Verdict (`devops review`, `profile.json`)**:
  - A finding the verifier was shown and its reply gave no verdict on carries the note `verifier-no-verdict`, and one whose verifier reply held no verdicts that could be read carries `verifier-reply-unparsed`. In session `20261001-224227`, 233 of 357 unverified findings carried no note, so a reader could not tell them apart (#846).
  - A finding the verifier judged and left unverified says why: `verifier-self-refutation` when its invalidation rested only on the finding's own claim and was withdrawn, and `verifier-inconclusive` when the verdict neither confirmed, refuted nor found a mitigation, or both confirmed and refuted. A finding the verifier was shown no longer stays unverified without a note. In session `20261002-214641`, 9 reported findings had no verdict and no note: 5 withdrawn self-refutations, 3 cut replies and 1 inconclusive verdict (#846).
  - A file whose verification failed is still reported, and each of its unverified findings carries `verification-unavailable` with the error's type, as when the verifier cannot be reached. Before, they were reported with no note (#846).
  - `profile.json` counts each unverified finding's note by kind under `verdict_distributions.verification_note`: `verifier-no-verdict`, `verifier-reply-unparsed`, `verifier-reply-cut`, `verifier-self-refutation`, `verifier-inconclusive`, `verification-unavailable`, `criteria-non-discriminating`, `other` for a note in words, and `none` for a finding verification never reached (#846).
  - A finding whose criteria passed both ways keeps the note `criteria-non-discriminating` when the verifier's verdict on it is inconclusive. A verdict, or one of the other notes above, replaces it (#846).
- **The Review Report Counts Timed-Out Criteria (`devops review path|branch|pr`, `devops_cli.ai.review.pipeline`)**:
  - `review.md` gains an "Executable Criteria" section after "Verdict Field Distributions", which counts the executable criteria of the session's candidate findings as Passed, Failed, Timed Out and Not Run. Only a criterion that ran to a non-zero exit is counted as failed: one stopped at its time limit is timed out, and one the sandbox could not start (no bubblewrap, a spawn error) or stopped for its output is not run, as the verdict already treated it. A session without executable criteria has no such section (#847).
  - `CriterionExecutionResult` and `HostSandboxResult` carry `timed_out`, set when the sandbox stopped the command at its limit, so `findings.json` and `candidates.json` record it for each criterion. Sessions saved earlier load with `timed_out` false (#847).
- **Judging Candidates the Review Dropped (`devops review findings --candidates`, `devops review verify --candidate`)**:
  - `devops review findings --candidates` lists candidates.json, every finding the review raised, including the ones verification invalidated, which never reach findings.json (#949).
  - `devops review verify --candidate <n>` gives a verdict on a candidate. A candidate marked VERIFIED or MITIGATED moves into findings.json with `verified_by` set to the adjudicator, and a later verdict on that candidate updates its copy there (#949).
  - A verdict given with `--index` is recorded on the candidate the finding reports in candidates.json as well, so `review findings --candidates` and review history never keep a verdict findings.json withdrew (#949).
  - A candidate's copy in findings.json is the finding of the same persona, title and location, or the copy a verdict moved, which names its candidate (`moved_from_candidate`). A verdict on one persona's candidate leaves alone the finding another persona reported with the same title at the same location, and a candidate its copy cannot tell apart from another, of the same persona, title, location and description, is refused with the number to judge with `--index` (#949).
  - A candidate whose defect findings.json already reports under another title, because consolidation merged it or kept another persona's report of it, is not added a second time. The command names that finding, to be judged with `--index` instead (#949).
- **Verdict Provenance (`devops review verify --adjudicator`, MCP `verify_finding`)**:
  - `--adjudicator {human,agent}` records who gave a verdict, `human` by default. The MCP `verify_finding` tool always records `agent`, since MCP clients are untrusted (#949).
  - Only a person's verdict teaches the learned catalog (INVALIDATED) or records a mitigation in the ledger (MITIGATED) (#949).
  - Review history ranks a subject's sessions by a person's verdicts, those on candidates kept out of findings.json included, then by findings with any verdict. An agent's verdict counts in neither, so it never raises its session above another of the same subject (#949).
  - An agent's verdict on a finding a person judged, through `--adjudicator agent` or the MCP tool, is refused, so an agent can neither replace a person's verdict nor withdraw what it recorded in the catalog and ledger (#949).
- **A Person's Verdict Suppresses That Claim in Later Reviews (`devops review verify`, `devops review`)**:
  - A person's INVALIDATED verdict records the one claim it disproved in the learned catalog (`.data/common_hallucinations.json`): the project the code belongs to, the file relative to its checkout, the first line its location cites, a hash of the lines it cites, each stripped of surrounding whitespace, and the identifiers of those lines that the title names, or the description when the title names none. A later review of that project invalidates a finding making the same claim at the same line with `deterministic:person_verdict` before any model is asked about it, whichever tool or persona raised it and however it is worded: a Semgrep `exec` finding a person judged suppresses Bandit's B102 at the same line, as review session `20261002-214641` reported it. A verdict on one `except Exception as err:` handler reaches no other handler that reads the same, and a verdict in one repository no other repository's identical code, though both share a data directory. A change to the cited lines, or an edit above them that moves them, raises the claim again (#950).
  - A suppression needs a code identifier. Python's keywords (`in`, `for`, `with`, ...) and common English words never count, and in a prose or configuration file, such as Markdown, YAML or JSON, only a name with an underscore or a camelCase hump does. A verdict on a finding that names no such identifier of its cited lines, or whose session recorded no code at its location, records no entry and says so; the verdict itself still stands (#950).
  - Every saved finding carries `cited_code`: the project, the file relative to its checkout, the first line and the lines its location cites as the review read them, at most 40, with secrets masked and only from a non-secret file inside the reviewed checkout. A verdict keys its claim on that record only, never on the file as it reads when the verdict is given, which may hold code the person never saw; a verdict on a session saved before this change records nothing (#950).
  - `devops review pr` writes the PR head into a temporary directory named after the checkout it runs in, so the review is shown that checkout's judged claims and suppresses them in the head's files (#950).
- **`devops ai prompt-eval --include-deterministic`**:
  - Counts the records a deterministic check labelled, which are now left out by default (#950).
- **Review Prompt Consistency Tests (`tests/test_review_prompt_consistency.py`)**:
  - A test fails when a prompt file under `ai/tasks/` or `ai/personas/` is loaded nowhere, when a prompt a reviewer reads names what `review.md` or the verifier calls a non-defect (`http://`, `NotImplementedError`, masking markers, `default_factory`, `os.kill(pid, 0)`) anywhere but the prompt that says so, and when any prompt asks for a CVE ID or lets a finding stand on an advisory identifier. Others pin the threat model and evidence bar below, a single masking-marker rule in the reviewer and the verifier that names only markers `mask_secrets` writes, a test rule that keeps a real credential or vulnerability in a test file reportable, an untrusted source in every security rule that requires a guard, a JSON reply format in the served `code_review_prompt` MCP prompt and no partial field list on a review page, which the reply schema answers, the reviewer's severity bands in the verifier, a measurement that runs the persona its baseline ran and counts only the review tool's masking markers as a failure, example replies without `HIGH`, `CRITICAL` or a confidence of 0.9 or more, and `.devops/review.md` within the 8,000 characters a review reads (#951).
- **Docs-Claims Tests for the Review Loop**:
  - Every metric `docs/SELF_IMPROVEMENT.md` names is a registered instrument, every `devops review` and `devops ai review` example in AGENTS.md, the hand-written pages under `docs/` and the knowledge base parses with the Typer app, and every path they name for the feedback dataset is the one the exporter writes (`tests/test_docs_review_loop.py`). Markdown is read with markdown-it-py, now a declared development dependency (#952).
- **A Deploy Path for Every LLM Manifest (`tests/test_k8s_llm_gateway.py`)**:
  - A test fails on any manifest under `k8s/llm` that no kustomization, deploy-stack manifest list or Helm release applies (#953).
- **Registered Telemetry Variables (`DEVOPS_CLI_TELEMETRY_ENABLED`, `DEVOPS_CLI_TELEMETRY_ENDPOINT`, `devops_cli.telemetry.tracer`)**:
  - The two variables set `telemetry.enabled` and `telemetry.endpoint` the way every other `DEVOPS_CLI_*` variable sets its key, and `docs/CONFIGURATION.md` and `docs/ENV_VARS.md` list them. The tracer takes both from the settings, so a variable, the project config and the user config each count in the documented order (#956).
- **Grafana Service & Cluster Workload Graphs Sum & Average Lines (`k8s.monitoring.dashboards`)**:
  - Added dedicated, properly labeled `Total (Sum)` and `Average (Mean)` PromQL baseline lines to primary multi-series timeseries graphs across `sre-service.json`, `ingress-tunnel.json`, `k8s-views-nodes.json`, `k8s-views-pods.json`, and `llm-stack.json` (#968).
  - Maintained 100% static lint conformance with zero errors across all 12 shipped Grafana dashboards, verified by `devops grafana dashboards lint` and `test_dashboards_contain_properly_labeled_sum_and_average_lines` (#968).
- **RAG Queries Timed by Stage, and Qdrant Retries Counted (`devops_cli.ai.rag.retriever`, `devops_cli.ai.rag.qdrant`, `devops_cli.telemetry.instruments`)**:
  - Each RAG query observes `devops_cli_rag_query_duration_ms` once per stage under a `stage` label: `embedding` (the query's embedding request), `search` (the Qdrant searches), `ranking` (projection, hybrid fusion and reranking) and `total` (the whole query, which the unlabelled observation used to be). Each observation also carries `outcome` (`ok` or `error`): a stage that fails, such as an embedding that times out, records its time as `error`, so the panels show the tail it causes (#975).
  - `devops_cli_qdrant_retries_total` counts each Qdrant request retried after a transient error, by `operation` (the client method, such as `search_points`) and `error_type`. The Qdrant client raises every transport error as a `ResponseHandlingException`, so `error_type` is the class of the error inside it, such as `RemoteProtocolError` for a dropped keep-alive connection or `ReadTimeout` for a request that waited out its timeout, and not the wrapper's class, which every network error shared. Collection and file names stay in the log, not the labels (#975).
- **Per-Stage RAG Latency and Qdrant Retry Panels (`k8s/monitoring/dashboards/devops-cli.json`)**:
  - The dashboard's first row gains "RAG Query Stage Latency (p95)", the p95 of `embedding`, `search` and `ranking` over the last hour, and "Qdrant Retries by Operation and Error", retries per hour. The rows below move down one panel height (#975).
- **Pyroscope UI Endpoints, Port-Forwarding, and Grafana Dashboards (`k8s.monitoring`)**:
  - Added `--pyroscope-port` (default 4040) to `devops k8s port-forward` and enabled continuous profiling forwarding for `svc/pyroscope:4040` (#977).
  - Announced `Pyroscope UI: http://localhost:4040 (namespace: monitoring)` in `devops k8s deploy-stack` connection summary (#977).
  - Added `pyroscope.url` service discovery to `devops k8s configure-urls` for cluster-native proxy and nodeport addressing (#977).
  - Added dedicated Continuous Profiling dashboard (`pyroscope.json`, UID `devops-pyroscope`) and integrated Pyroscope CPU and Memory flamegraph panels into `sre-service.json` (#977).
- **The Whole Review on the Terminal (`devops review path|branch|pr --full`)**:
  - `--full` prints every finding with its detail panel, every dependency and every network reference, as reviews printed them before (#987).
- **Findings by Severity (`devops review findings --severity`)**:
  - `--severity` lists the findings of one severity and is repeatable. It takes any spelling a review accepts, so `informational` means INFO. Each finding keeps its number in findings.json, the one `devops review verify --index` takes, and `--severity` combines with the status filters and `--candidates` (#987).
- **Review Recall Set (`tests/fixtures/review_recall/recall_set.json`, `docs/SELF_IMPROVEMENT.md`)**:
  - The known real findings that review session `20261002-205520` did not generate, plus the two broad excepts in `ai/spend/pricing.py` it did, each with its file, revision, the line range of the defective construct, class and tracking issue. Tests in `tests/test_review_prompt_consistency.py` fail when no prompt that reaches a file names its class (the DevSecOps persona's *Where to Look*, or the page prompt for the file's kind), when the page prompt a file gets carries a rule that silenced the persona, when the persona keeps a rule that silenced it or lacks one this change restored, when a restored class may be reported above MEDIUM or LOW, and, in a clone that holds the revision, when a cited range no longer holds the finding's evidence (#1015).
  - `docs/SELF_IMPROVEMENT.md` describes how a person scores recall on the set beside #951's corpus A/B: three fresh reviews (`--no-cache`, `--no-static-scan`) of the set's files per arm, a script that counts the samples that found and that reported each finding and lists every other finding on the set's files for labelling, a bar of 2 of 3 samples for each Network Exposure finding that counts only matches describing the set's defect, with the other classes counted, not gated, a precision guard on the files session `20261002-205520` reported findings on, and a review from both arms of the NetworkPolicies, Ingress and Service manifests and security documents the restored rules reach (#1015).
- **A Background Tier Group, `devops-background` (`k8s/llm/gateway/configmap.yaml`)**:
  - `devops-background` is the only chat group with a deployment on ollama-48gib-slow: `qwen3-coder:30b`, with a 1,100 s timeout, under the review client's 1,200 s read timeout so a call the client abandoned frees the tier's one slot, and no gateway retries. It sets no `max_input_tokens`, because LiteLLM would apply that window to every `qwen3-coder:30b` deployment. `devops-review` falls back to it once its own retries fail, gateway timeouts included. `devops-chat` does not, because fallbacks chain and compose or reasoning failures would reach it through `devops-coder` (#1064).
  - `k8s/README.md` shows how `devops review path --watch` (analysis, verification and compose), `devops ai pipeline`, `devops ai agents` and `devops ai analyze` use it through environment overrides with `DEVOPS_CLI_AI_MAX_RETRIES=1`, never through `config.yaml` (#1064).
- **The Review Profile Keeps Why Each Analyzer Failed and How Long Each Ran (`profile.json`)**:
  - `static_analyzer_reasons` holds the reason review.md gives for each analyzer that failed, and `static_analyzer_seconds` how many seconds each analyzer's scans ran (#1079).
- **Each Node's Journal Reaches Loki Through the Alloy Log Collector (`k8s/monitoring/k8s-monitoring-values.yaml`)**:
  - The chart's node logs feature (`nodeLogs`) runs on the `alloy-logs` DaemonSet that already ships pod logs and reads `/var/log/journal` on every node, so no agent is installed on a host. It keeps kernel lines at every priority (GPU Xid errors, machine checks, thermal events), the `k3s`, `k3s-agent`, `nvidia-power-limit`, `containerd` and `systemd-journald` units and systemd's own start, stop, exit and restart lines about them at info and above, and every other line at warning and above. Lines carry `job="integrations/kubernetes/journal"`, `instance` (the node), `unit`, `transport` and `level`, with `boot_id` as structured metadata. On 2026-10-03 all four nodes lost power together three times, and the timeline had to be rebuilt from each host's local journal (#1080).
  - Each unit may send 1 line/s after a burst of 10,000, which covers a boot and the 8 hours the reader goes back after a restart; kernel lines have no limit. Alloy counts the lines the limit drops per unit in `loki_process_dropped_lines_by_label_total` on its own `/metrics`, which Prometheus does not scrape. Measured on the four live nodes' journals for 2026-10-01 and 2026-10-02, the filter keeps 6.7 MB of text a day across the cluster, 7.5 MB on the busiest day, about 0.6% of the 1.27 GB a day Loki already takes in. The busiest unit peaked at 1,091 lines in a minute and 2,887 in an hour, inside the limit. The budget is 20 MB of text a day (#1080).
  - Loki keeps journal lines for 30 days only once #550's compactor retention (`retention_period: 720h` with `compactor.retention_enabled`) is applied; until then Loki deletes nothing by age. At the 5.7 times compression of Loki's current chunks, the 6.7 MB of text a day is about 1.2 MB a day on disk, 36 MB over 30 days, and the 20 MB a day budget at most about 106 MB (#1080).
- **Prometheus Keeps the Series That Explain a Host Failure (`k8s/monitoring/k8s-monitoring-values.yaml`)**:
  - The host metrics allowlist adds `node_boot_time_seconds`, `node_hwmon_temp_celsius`, `node_hwmon_chip_names`, `node_pressure_.*`, `node_edac_correctable_errors_total`, `node_edac_uncorrectable_errors_total`, `node_nvme_info` and `node_systemd_unit_state`, and names `node_filesystem_avail_bytes` and `node_filesystem_size_bytes`, which the chart's default list already keeps (#1080).
  - node-exporter's systemd collector, off by default, reports only the units above. It reaches the host's D-Bus socket through the node root the chart already mounts at `/host/root` (`DBUS_SYSTEM_BUS_ADDRESS`). The chart's filesystem-type exclusion is repeated, because Helm replaces the argument list (#1080).
  - Counted from each node's exporter before the change, the list adds 41 to 66 series per node, 207 across the four live nodes, against a budget of 100 per node: 0.3% of Prometheus's 63,864 head series and 3.5 of its 874 samples/s, about 18 MB over 30 days. Prometheus keeps 30 days by time and has no size cap, so the new series keep 30 days of history from the apply (#1080).

### Changed
- **One JSON Shape for Every Corpus Score (`devops review corpus score --json`)**:
  - `--json` and the kept run's results are the arm's score for any number of runs. The single-session figures moved under `scores[0]` (#413).
- **Loki's Volume Holds 30 Days of Logs (`k8s/logging/loki-values.yaml`)**:
  - `singleBinary.persistence.size` is `20Gi`, up from `2Gi`. Measured on 2026-10-03, pod logs arrived at 0.5 to 1.3 GB a day from 2026-09-30 on, 1.3 GB on the busiest day, and are stored at about 11:1. The host journals that #1080 adds are estimated from journal file growth at about 0.04 GB a day, and the sizing allows 0.2 GB a day for them. 30 days take about 4.5 GB, and about 9.4 GB at a pessimistic 5:1 with every day as busy as the busiest (#550).
  - Kubernetes does not let an upgrade change a StatefulSet's `volumeClaimTemplates`, and local-path cannot expand a claim in place. Applying the new size takes deleting the StatefulSet with `--cascade=orphan` and rebinding the existing volume to the new claim, which keeps the logs already stored. The task file lists the commands (#550).
- **Prometheus Keeps 30 Days Under a Size Cap That Does Not Bind First (`k8s/monitoring/prometheus-values.yaml`)**:
  - `server.retentionSize: 16GB` (16 GiB, 80% of the 20Gi volume) caps the TSDB, and `server.retention: 30d` still decides what is deleted. Measured on 2026-10-03, 30 days take about 5 GB, and #1080's roughly 270 host series add under 0.1 GB (#550).
- **The `structural-invariants` Hook Checks Nesting Only (`.pre-commit-config.yaml`, `devops_cli.security.structural_invariants`)**:
  - The hook no longer counts complexity or prints its "Not blocking" complexity note, because complexity is now Ruff's `C901`. `breaches` and `check_structural_invariants` return only the nesting breaches and take no `max_complexity`, `measure` returns a function's nesting depth, and `MAX_COMPLEXITY` is gone. Nesting is measured as before: the old and new measures agree on all 14,749 functions in `src/` and `tests/` (#586).
  - `measure` walks a function with its own stack instead of recursing, so a long expression such as a 3,000-term sum is measured instead of stopping the hook with a `RecursionError` traceback. The released hook already failed that way at 3,000 terms. A parser stack overflow is reported as a file the hook could not parse (#586).
  - Two tests are removed. `test_complexity_is_reported_without_blocking` started a hook subprocess, and `test_filesystem_get_tools_complexity` guarded a function that `C901` now covers (#586).
- **LLM Spans Write the GenAI Conventions' Keys, Each Once (`devops_cli.ai.client`, `devops_cli.ai.direct`)**:
  - `ai.llm.dispatch` and the stream span are CLIENT spans of the conventions' inference type, with `gen_ai.operation.name` (`chat`), `gen_ai.provider.name`, `gen_ai.request.model`, and `server.address` and `server.port` when one backend host served the request. The stream span also sets `gen_ai.request.stream`. Token usage, the response model and finish reasons are written only on `ai.llm.dispatch`, so a request's usage is counted once, and no old key is written beside its replacement (#588).
  - Saved Jaeger or Logfire queries need these renames. Keys the conventions do not define moved under `llm.*` (#588):
    - span `gen_ai.chat` → `ai.llm.chat`, span `gen_ai.stream` → `ai.llm.stream`
    - `gen_ai.system` → `gen_ai.provider.name`, with `claude` written as `anthropic`
    - `gen_ai.usage.prompt_tokens` → `gen_ai.usage.input_tokens`, `gen_ai.usage.completion_tokens` → `gen_ai.usage.output_tokens`
    - `gen_ai.usage.total_tokens` → removed (it is input plus output)
    - `gen_ai.server.address`, which held the backend description → `server.address` (the host) and `server.port`
    - `gen_ai.response.model`, which held the backend description or `cache` → the model the provider reports, unset when unknown
    - `gen_ai.ttft_seconds`, `gen_ai.time_to_first_token_ms` → `gen_ai.response.time_to_first_chunk` (seconds)
    - `gen_ai.tokens_per_second`, `gen_ai.token_rate_tok_per_sec` → `llm.tokens_per_second`
    - `gen_ai.wall_seconds` → `llm.wall_seconds`, `gen_ai.processing_seconds` → `llm.processing_seconds`
    - `gen_ai.duration_seconds` → removed with `record_llm_metrics`
    - `gen_ai.server.served_by` → `llm.served_by`
    - `gen_ai.usage.cost_usd` → `llm.usage.cost_usd`
    - `gen_ai.cached` → `llm.cached`
    - `gen_ai.request.priority` → `llm.request.priority`
    - `gen_ai.request.enable_thinking`, `gen_ai.enable_thinking` → `llm.request.enable_thinking`
    - `gen_ai.request.message_count`, `gen_ai.messages_count` → `llm.request.message_count`
    - `gen_ai.request.system_prompt_length` → `llm.request.system_prompt_length`
    - `gen_ai.prompt_preview` → `llm.prompt_preview`, `gen_ai.response_preview` → `llm.response_preview`
    - `gen_ai.thinking` → `llm.response.thinking`
    - `gen_ai.sanitize` → `llm.stream.sanitize`
    - `gen_ai.stream_chunks_count` → `llm.stream.chunk_count`
- **A Stream Ends Only on Its Provider's Final Frame (`devops ai chat`, `devops_cli.ai.client`)**:
  - OpenAI-compatible and Anthropic streams are read with httpx2's `EventSource`, which splits lines on CR and LF alone, and Ollama streams are split on LF from the raw bytes. A delta holding a raw U+2028, which the old line reader split in two and dropped, now arrives intact. Each event, and each unterminated Ollama line, is limited to 1 MiB (`DEFAULT_AI_STREAM_MAX_EVENT_BYTES`), and the whole stream is still limited to 50 MiB. Chunks are still yielded as they arrive (#599).
  - A stream is complete on a chunk with a finish reason or `[DONE]` (OpenAI-compatible), `message_stop` (Anthropic) or `done: true` (Ollama). A stream that ends before that, an error frame, and an event stream sent with another content type raise `AIClientError`, where each used to return its partial text as a whole reply. An error frame's message is masked and cut to 256 characters. A stream cut after it yielded output is not replayed on the next Ollama host (#599).
  - A stream that fails after yielding output records its spend with finish reason `error`, then re-raises. One that fails before its first chunk records nothing, as a failed non-streamed call records nothing (#599).
- **`devops review stats` Counts Each Review Subject Once (`devops review stats`)**:
  - Its tables count one session per subject, so a re-review or each `devops review benchmark` run no longer adds its findings again. `Total Sessions` is replaced by `Sessions: N (counted C: R repeat sessions collapsed, T target-only, U unkeyed)`. Its findings still come from findings.json, the findings each session reported (#607).
- **A Task File Ticks a Box Only for Work That Is Done (`docs/agent/tasks/`, `AGENTS.md`)**:
  - `tests/test_agent_task_files.py` fails on an unchecked box outside a code fence. Work not done is a plain bullet naming its follow-up issue, and a check only a person can run is a plain bullet starting "Pending a person:". The 17 task files that held unchecked boxes are brought into line, and `AGENTS.md` no longer asks for typed verification results: the PR's passing checks are the verification (#704).
- **The PR Template and the Release PR Body Ask Only What No Check Decides (`.github/pull_request_template.md`, `devops release`)**:
  - The template asks for a summary, the type of change, the base branch, `Closes #<issue>` and the task file. Its 15-box quality-gate checklist is gone, and so is the example closing reference in a comment, which read as closing that issue in any body that kept it (#704).
  - The release PR body no longer carries the seven quality boxes it ticked on every ready release PR without reading anything (#704).
- **Board Statuses and Fields Follow ADR 0001 (`.github/project-template.json`, `devops gh project sync`)**:
  - Status options are New, Ready, In Progress, In Review, Done and Blocked. Category and the Milestone text field are gone, and the Value vs Effort view groups by Value. An unset Status and the `status/backlog` label now read as New, and reconcile no longer writes the Milestone field the board mirrors (#739).
  - `devops gh project sync` creates missing fields and never edits an existing field's options. GitHub gives every option it is sent a new id, so once the template changed its option request would have cleared Status on every card. No command edits an existing board's options; a person makes the edits `devops roadmap migrate` lists in the board's field settings, which keep ids (#739).
  - `devops gh project workflows list` expects New on add and reopen and In Review on a linked pull request, and no longer asks for the auto-add, auto-close or auto-archive workflows (#739).
  - `docs/ROADMAP.md` carries a banner: GitHub is its source, `devops roadmap render` regenerates it at the next cut, and work is added by opening an issue (#739).
- **Readiness Blocks a PR Into a Release Branch That Closes Another Release's Item (`devops pr check-readiness`)**:
  - A PR into `release/vX.Y.Z` is blocked when the one issue it closes is not in release vX.Y.Z. The blocker names the issue and the release it is in, or says it is in the backlog. PRs into the default branch, the release PR and release-process PRs are not affected (#740).
- **A Job Record the Store Can't Read Stops the Read (`devops_cli.roadmap.github_store`)**:
  - A card's job record that is not a JSON object, or gives a key the store knows a value that is not text, now fails the read and names the card, where it used to read as empty, which made an admitted item look newly added. A key this version doesn't know, such as one a newer version writes, is left out of the read and kept by every write (#740).
- **A Field Write Records the Job's Value First (`devops_cli.roadmap.github_store`)**:
  - The GitHub adapter's `set_field` writes the job record, with the value and any marks given with it, before it sets the field, so a write that stops between GitHub's two calls never leaves a field the job changed with no record of it (#740).
- **`devops gh milestones edit` and `close` Take a Version (`devops gh milestones`)**:
  - Both take a version, with or without the leading `v`, and no longer a milestone number. The milestone commands and the milestone close after `devops release tag --push` run on the roadmap store (#768).
- **A Mitigated Finding Is Not a Verified One (`devops review path|branch|pr`, `devops review verify`, `devops_cli.ai.review.verdicts`)**:
  - A MITIGATED verdict, a model's or a person's, sets `verified=False`, and so does the merge of two findings whose best verdict is MITIGATED. MITIGATED defaulted to verified, so 11 of the 28 mitigations in review session `20261001-224227` counted as verified defects (#845).
- **The Verifier Is Told What a Mitigation Needs (`devops review path|branch|pr`, `ai/tasks/verify_finding_system.md`)**:
  - The verifier's instructions say a perimeter file is a repository-relative path to code or configuration in the reviewed tree, never documentation such as the project's conventions, that the mechanism names an identifier in backticks which a perimeter file or the finding's file holds, and that a mechanism describing the defect is no mitigation. The prompt digest changes, so cached verifier replies are not replayed (#845).
- **Criteria Settle a Verdict Only on Evidence About the Cited Code (`devops review`)**:
  - A passing verification or invalidation criterion settles a verdict only when it runs the code the finding cites and checks the outcome. A `python -c` script counts when it checks a value from the cited code: a name it imports from the cited module, the cited file read and parsed (`json.loads`, `yaml.safe_load`, `tomllib.loads`), or anything computed from either. The check is an `assert` over such a value, a `raise` or failing exit under a condition over one, or `sys.exit`, `exit` or `raise SystemExit` of a comparison or `not` over one. In session `20261001-224227`, 36 findings were VERIFIED by criteria and none of their 37 passing commands checked the cited code; one was a regex echoed against a literal, on a CRITICAL finding that cited CVE-2021-44228. Replayed with their recorded results, all 36 of that session's criteria-VERIFIED findings and 59 of its 61 criteria-INVALIDATED findings now go to the verifier (#846).
  - These never count: `grep`, `git grep`, `git log`, `wc`, `cat`, `head`, `tail`, `find` and every other command; a script that inspects code (`hasattr`, `inspect.getsource`, `__code__`) instead of running it; a search of a cited file's text (`'os.system' in Path('app.py').read_text()`, `re.search` over it), so a cited Python file counts only through its import; a test that something exists (`assert f`, `f is not None`, `Path(...).exists()`, `os.path.isfile(...)`); a check that does not depend on the cited code (`import app; assert 1 == 1`, `raise SystemExit(0)`, `exit(0)`); and `sys.exit(f(...))`, which exits 0 whenever `f` returns None (#846).
  - A passing invalidation criterion no longer dismisses a finding whatever it runs. A grep that found the line the finding cites settled INVALIDATED, a verdict the verifier never saw (#846).
  - A command that does not count is still recorded in `criteria_execution_results` and leaves the finding to the verifier. Only commands that count are listed in `verified_criteria_matched` and `invalidated_criteria_matched`, and criteria that settle nothing no longer give the finding a confidence (#846).
  - A verification and an invalidation criterion that both pass, whether or not they count, cannot tell the defect from its absence: the finding stays unverified with the note `criteria-non-discriminating` and goes to the verifier. In session `20261001-224227`, 215 findings had criteria that passed both ways (#846).
  - Inspection is read from the script's syntax tree instead of matched as text, so `content_type(...)` is no longer taken for `type(...)` (#846).
- **The Verifier Judges the Claim, Not the Pipeline's State (`devops review`)**:
  - The verifier is shown an allowlist of each finding's fields: its number, severity, location, title, description, fix, references, category, both criteria lists as written, and the observed and expected values. It is no longer shown the reviewer's confidence, status, reportability or reasoning, nor the criteria results with their run times. Verifying a finding again sends the same prompt byte for byte, so with the response cache on, verifying an unchanged file again replays the first reply instead of reaching the model. The run times made every prompt with executed criteria new, and the branch reviews of release/v0.2.25 replayed only 3 and 6 verifier replies. A field added to findings later stays out of the verifier prompt until it is added to the allowlist (#846).
  - A refutation cites a line only through a citation key such as `citation_line`. The `location` a verdict repeats and a line number in its reason no longer count, so a refutation without a citation leaves the finding unverified (#846).
  - A refutation of the finding's criteria rather than its claim (its reason calls them tautological, or says they only confirm the code exists) that cites no line leaves the finding unverified, noting why (#846).
- **Python Criteria Run Up to 30 s (`devops review path|branch|pr`, `devops_cli.ai.review.review_environment`)**:
  - A `python` or `python3` criterion runs for up to 30 s (`DEFAULT_CRITERIA_PYTHON_TIMEOUT_SECONDS`), since it imports the reviewed code; `grep`, `git` and the other commands keep 5 s. In the saved review sessions, 1,353 of 4,027 python criterion runs (34%) hit the 5 s limit, most of them while still importing the code they were to check (#847).
  - The limit was measured by replaying the 1,115 distinct python criteria that hit 5 s in 14 saved sessions, offline through the sandbox with the repository's `.venv` first on `PATH`, four at a time: half finished within 6.2 s, 95% within 15.4 s and 99% within 22.5 s, and 1,111 (99.6%) within 30 s. Two more finished by 36 s and two ran to the 60 s cap. A random 60 of them, run one at a time on a quiet host, all finished within 8.8 s, so most of the time past that is criteria contending with each other (#847).
  - A criterion that now finishes within the longer limit settles a verdict only as the evidence rule allows (#846): one that prints what the cited code returns still settles nothing, and one that asserts over it counts as evidence, which settles INVALIDATED as an invalidation criterion and leaves the finding to the verifier as a verification criterion. With the 30 s limit alone, a print-only criterion replayed at 6.8 s on a made-up HIGH finding ended VERIFIED with confidence 1.0 (#847).
- **Scanner Errors Become a Failed Outcome in One Place (`devops_cli.security.registry`)**:
  - `ScannerRegistry.scan_all` takes `names`, the scanners to run, every registered one by default, and `devops scan report` runs through it instead of its own loop. A scanner that raises is recorded as failed there, with its error as the reason. The `image` parameter is gone: `image=` is passed on to each scanner with the other keyword arguments (#915).
- **Item PRs Add a Changelog Fragment and Leave `CHANGELOG.md` and `docs/ROADMAP.md` to the Cut (`AGENTS.md`, `RELEASE_CYCLE.md`, `docs/agent/tasks/README.md`, `.github/pull_request_template.md`)**:
  - The rules say to add `changelog.d/<issue>.md` and not to edit `CHANGELOG.md` or `docs/ROADMAP.md` in an item PR, and that release-process PRs use `chore/open-vX.Y.Z` or `chore/cut-vX.Y.Z` branches. The entries that were under `## [Unreleased]` are now `changelog.d/593.md`, `changelog.d/704.md`, `changelog.d/739.md` and `changelog.d/768.md`, text unchanged (#933).
- **Review Reports Lead With What Was Verified (`devops review path|branch|pr`, `devops_cli.ai.review.stages.reporting`)**:
  - Findings rank reportable first, then VERIFIED, UNVERIFIED and MITIGATED, then by severity, location and title. A model's confidence no longer ranks them: in session `20261001-224227` UNVERIFIED findings at confidence 1.0 ranked above VERIFIED ones (#948).
  - The executive summary counts the findings by status, each status with its severities, and lists the findings verification never reached and the MITIGATED ones apart. The report's summary section and the terminal's Review Summary table count them the same way. The session's headline read "563 reportable findings (21 Critical, 263 High)" across every status (#948).
  - The headline names the defect classes that recur among VERIFIED findings, most severe first, then most frequent, the first three by name. A class seen once, a finding title or a CVE is never a theme, and Key Bad Patterns gives one line per recurring class. The headline used to name the first reference or title of the first-sorted findings, so CVE-2021-44228 on an UNVERIFIED finding headlined the session, and Key Bad Patterns ran to 280 bullets, 257 of them for a single finding (#948).
  - The analyzer line is computed from the scan: the analyzers that ran, the critical findings they reported, and those on built-in patterns only, failed or not installed. It was a literal, "with 0 critical findings", while Bandit, Semgrep and Pluto had failed, and it counted Gitleaks among the analyzers executed when only its built-in patterns ran (#948).
- **One Defect Taxonomy (`devops_cli.ai.review_schema`, `devops review stats`)**:
  - A finding's category is the CWE it cites, in its category or its references, as `CWE-<n>`, or else a class of the closed `DefectClass` enum named by the category's words or, with no category, the title's. The original is kept as `category_raw`. The persona has written no category since #951, so the pipeline assigns one. Session `20261001-224227`'s 148 category strings fall into 27 classes (#948).
  - The report's themes, its category baseline table and `devops review stats` group findings by one function, `resolve_finding_category`, which reads a finding saved by an earlier session the same way (#948).
- **Severities Capped by Their Evidence (`devops review path|branch|pr`)**:
  - Once verdicts are final, CRITICAL requires VERIFIED; a title hedged with "Potential", "May", "Could" or the like is MEDIUM at most; and a finding in a test or a document is LOW at most unless it concerns a verified secret, which a secret scanner's match counts as. A capped finding keeps the severity it was given as `severity_raw` in findings.json and candidates.json. Replayed over session `20261001-224227`, the 563 reported findings go from 21 CRITICAL and 263 HIGH to 5 and 165 (#948).
  - The caps apply when the report is written. A later verdict through `devops review verify` changes a finding's status, not its severity (#948).
  - A scanner's absolute path is read from the repository root, so a checkout under a directory named `tests` does not make every scanner finding a test finding (#948).
- **Planning Documents and Generated References Stay Off Persona Pages (`devops review path|branch|pr`)**:
  - Path, branch and pull request reviews keep `docs/ROADMAP.md`, `CHANGELOG.md`, `changelog.d/`, `docs/agent/tasks/`, `docs/adr/`, `docs/commands/*.md` and `docs/CLI_REFERENCE.md` off persona pages, as they kept lockfiles, with one predicate for all three. In the branch reviews of release/v0.2.25 those paths took 24-27% of the persona pages, and none of the findings raised on them held up. A file named as a path review's target is still reviewed (#948).
  - Gitleaks still reads every file kept off the pages, lockfiles included, and Semgrep does not. A secret it finds there is reported against that file at its severity, HIGH at most until verified, and never capped as a document finding (#948).
  - The verifier of a finding in such a file is sent the numbered lines around what the finding cites, or around the package a Trivy location such as `uv.lock:requests` names, never the whole file: this repository's uv.lock is 558 kB (#948).
- **Stable Finding Numbers (`devops review findings`, `devops review verify`, MCP `verify_finding`)**:
  - `review findings` numbers each finding by its place in findings.json, or in candidates.json with `--candidates`, whatever status filter it applies, and `verify --index` takes that number. Before, a filtered list was renumbered from 1, so `verify --index` put the verdict on a different finding (#949).
  - The MCP `verify_finding` tool counts from 1, as the CLI does, and refuses 0 (#949).
  - `verify --title` refuses a substring that more than one title contains, naming their numbers, instead of judging the first match. Naming more than one of `--index`, `--title` and `--candidate` is refused (#949).
- **No Default Verdict (`devops review verify`)**:
  - `--status` is required. It defaulted to INVALIDATED, so one careless call both invalidated a finding and taught the learned catalog (#949).
- **The Personas Are Shown What People Disproved (`devops review`)**:
  - The false positives in the persona prompt are the claims people judged in reviews of the target repository, the most often judged first, under "reported against this codebase". A repository with none is shown the curated builtin entries under their own heading, which no longer says they were reported against it, and another repository's judged claims are never shown. A judged claim's title and reason are masked and their prompt boundary tags escaped. The new heading prompts change the prompt digest (#950).
- **The Learned Catalog Learns Only From a Person (`devops_cli.ai.review.common_hallucinations`)**:
  - The deterministic checks (syntax, missing symbol, missing header, None dereference, catalog match) no longer write to the catalog, and a builtin catalog match is matched against the shipped entries only. Registering anything but a claim a person judged is refused (#950).
  - The ledger's writers take turns on a lock beside it (`common_hallucinations.json.lock`), and a ledger that cannot be read, or a record that does not validate, logs a warning instead of a debug message (#950).
- **A Verdict Withdraws What It No Longer Stands Behind (`devops review verify`)**:
  - Any verdict but INVALIDATED withdraws the learned-catalog entry a person's earlier INVALIDATED verdict on the finding recorded, and any but MITIGATED the ledger entry of an earlier MITIGATED one. Only a reset to UNVERIFIED withdrew them, so a finding a person judged INVALIDATED and then VERIFIED would have stayed suppressed in every later review as "A person judged this claim INVALIDATED" (#950).
- **`devops ai benchmark --type` Refuses an Unknown Type**:
  - `--type` (`--mode`) takes `auto`, `chat` or `embedding` and refuses anything else. `--type suite`, which this release removes, and any other unknown value ran the chat tasks benchmark, which calls models; the `embed` and `embeddings` spellings are refused as well (#950).
- **`devops review export-feedback` Appends to One Dataset**:
  - The export appends to the configured dataset, `.data/feedback_dataset.jsonl` (`data.feedback_dataset_path`), skipping each finding whose session, persona, location, title and verdict the dataset already holds, so a later verdict on a finding is appended rather than lost. It wrote the file over each time (#950).
  - It reads each session's candidates.json beside findings.json, where the findings the review kept out of its report keep their verdicts, so the default `--status INVALIDATED` sees the review's invalidations (#950).
  - Each record carries the session's `subject`, and the finding's `category`, `references` and `cited_excerpt`, the excerpt of its cited code (#950).
  - An export that finds nothing new leaves the dataset as it was, and says so (#950).
  - The documentation, the AI and RAG cheatsheet among it, names that one path; it named `.data/agent/`, `.data/reviews/` and `.data/feedback.jsonl` variants (#950).
- **`devops ai prompt-eval` Reports per Labeller**:
  - Each count is reported for each labeller (`human`, `agent`, `llm`, `criteria`, `unknown`, ...), and a record a deterministic check labelled (`deterministic:*`) is counted as excluded: scoring the deterministic layer against its own labels is circular. A claim a person judged is left out of the replay, so the layer is not credited with repeating that person's label (#950).
- **Review Prompts State a Threat Model and an Evidence Bar (`devops review`)**:
  - The DevSecOps persona says what is untrusted (network and fetched content, model output, pull request and issue text, repositories under review, Kubernetes and cloud API data, server requests, MCP and tool-call arguments) and what is trusted (the operator, their config files, environment and arguments, and values the code builds). A vulnerability is a quoted source, the sink it reaches and the missing check between them; the persona returns no finding when it cannot quote them. It no longer asks for CVE IDs: dependency advisories come from the scanners (#951).
  - Severity follows reachability. CRITICAL needs an untrusted input that reaches code execution, credential disclosure or a write outside its root, with every step quoted; a missing guard on trusted input is LOW where the project's conventions require it, and otherwise no finding. Trusted and untrusted input are what the project's conventions say; where they give no threat model, the shared prompt states a default one, so every persona's severity bands are defined (#951).
  - The error-detail rule (CWE-209) asks reviewers to bound untrusted strings rather than every caller-supplied one, and the verifier verifies an untrusted string or argument that reaches an exception detail, a log or a file path without its check, instead of verifying with no source and no sink (#951).
  - Reviewers report only what they can see. The rule it replaces let them report an unchecked assumption at a lower confidence, and in session `20261001-224227` all 357 findings verification left unverified were reported. A fix is replacement code for the cited lines, `observed_value` is copied from them, and an executable criterion imports the cited code and asserts the outcome; a command that finds, imports or prints code is a sentence with `"executable": false` (#951).
  - A finding about a test itself is only a test that cannot fail, while a real credential or a genuine vulnerability in a test file is still reported, as the verifier's rule for tests and its "never invalidate" rule now both say. A documentation finding is a statement the code contradicts, a broken relative link, or a command, option or key that does not exist; roadmaps, changelogs, task files and decision records get none. The configuration and persona checklists name defects instead of mandates, and no longer ask for `http://` to be flagged, which `review.md` and the verifier call intended inside a cluster (#951).
  - The verifier verifies a finding only when it can quote the defective line, and for a security claim the untrusted source and the sink. It refutes a claim that needs an attacker to control the operator's own input unless the project's conventions require the guard, refutes a finding that a check in the shown code makes impossible, and leaves a finding unverified when the deciding code is not shown. Its two rules on masking markers, which disagreed, are one, and it names only the markers the review tool writes, of the form `<masked-kind>`. A claim that one is invalid syntax, an undefined name or a broken value is refuted, and a claim that the value behind it is a real secret stands. A bare `<masked>`, `***REDACTED***` or any other mask is the file's own text, so a generated page that shows `<masked>` as a default is no longer taken for a redaction (#951).
  - The verifier no longer lets a dependency claim stand on a "real, lookup-able" CVE or GHSA identifier, which it cannot look up. Advisories come from the scanners, whose findings carry the identifier in a bracketed title at a lockfile; any other finding that rests on an advisory identifier, against a dependency or against code, is refuted. The placeholder-advisory verdict gives the same reason (#951).
  - The verifier rates severity on the reviewer's bands, which it had not been given although its severity replaces the reviewer's (#951).
  - The reviewer's and the verifier's example replies no longer show `HIGH` or a confidence of `0.95`. The verifier's verified example, an untrusted path traversal with every step quoted, lists every severity instead of naming one the bands do not give it (#951).
  - The `code_review_prompt` MCP prompt, which serves the code review rules on their own without the pipeline's reply schema, asks for one JSON object of findings (`severity`, `location`, `title`, `description`, `fix`) and a summary. The format is added where MCP composes the prompt, so the pipeline's review pages, answered in the reply schema, name no field list of their own (#951).
  - The prompt digest changes, so reviews from before and after this change are separate arms of a prompt benchmark. `docs/SELF_IMPROVEMENT.md` records the A/B measurement, which a person runs, with each arm reviewing the corpus under its own `.devops/review.md` and with the default DevSecOps persona, the only one the baseline session ran. Its `masked` failure count takes only findings about the review tool's `<masked-kind>` markers, and lists findings about a bare `<masked>`, the file's own text, apart as the known-positive check (#951).
- **`devops ai chat` Cites Advisories Only From Tool Output**:
  - The chat prompt no longer asks for CVE identifiers (#951).
- **The Persona Reply Schema Holds Only What a Reviewer Writes (`devops_cli.ai.review_schema`)**:
  - The fields of `Finding` and `ReviewResult` that the pipeline owns (verdicts, criteria results, citations, confidence, the recommendation, scanner and dependency data) are left out of their JSON schema, which the persona system prompt carries as the reply format. The schema falls from 8,220 to 1,674 characters. Replies and saved findings still parse every field. Reviewers are no longer asked for a `category`, so per-category metrics infer it (#951).
- **devops-cli's Own Review Exemptions Live in `.devops/review.md`**:
  - `.devops/review.md` gains this repository's trusted and untrusted inputs, where a tree devops-cli reviews, scans, analyzes or ingests is untrusted even when it is the user's own, and the facts about its own code that `review.md` and the verifier sent to every project's review: model backend URLs, offline URL parsing, empty ledgers, GraphQL payloads, Prometheus queries, hardware daemonsets, LLM egress policies, decommissioned backends, Jaeger v2, metric labels, Tenacity retries and the shared client pool. Its NodePort rule, which named a manifest path that does not exist, covers every NodePort in the `k8s/` manifests and Helm values, as the verifier's dropped rule did. The shared rule that GitHub logins need no case folding is dropped rather than moved: logins are case-insensitive, so it hid real bugs (#951).
- **`docs/SELF_IMPROVEMENT.md` Describes the Review Loop as It Runs**:
  - Section 1 follows a review through its six stages, the verdicts `devops review verify` records, what a person's verdict teaches (the learned catalog, the mitigations ledger, review history), the feedback dataset and its one reader, and where each kind of review data lives, naming the file and line of each step. It says what the loop does not do: there is no `performance` or `sre` persona and no ensemble by default, `devops review verify` runs nothing, the export reaches no RAG index and no prompt, a persona does not look the catalog up, and `review_output_instruction.md` and `--summary` belong to a path no CLI review takes (#952).
  - Section 2 follows the four steps of `tasks/review.md` instead of five phases, and section 3's remediation workflow records an agent's verdict with `--adjudicator agent` and says what it changes (#952).
  - Section 4 lists the two metrics a review sends, `devops_cli_review_duration_seconds` and `devops_cli_findings_total`, with their labels and the review's trace spans; it listed five metrics no code sends. Section 5.6 says where each calibration signal is read (#952).
  - A calibration record for review session `20261001-224227` gives its counts (903 candidates, 563 reported, 178 VERIFIED), the hand triage (489 of the 563 false, 46 confirmed and none above MEDIUM, 163 of the 178 VERIFIED false), the nine failure signatures the prompt A/B counts, and the mechanism each failure now has (#952).
- **AGENTS.md, the Knowledge Base and `CONTEXT.md` Agree With It**:
  - AGENTS.md no longer says the feedback export grounds RAG or refines prompts, says the default review runs the DevSecOps persona alone, describes what a review enforces about CVE citations, and tells agents to file a candidate issue for friction, an interface inconsistency, a bad pattern or a suggestion instead of adding it to `docs/ROADMAP.md` (ADR 0001). The generator's devops-cli template carries the same rules (#952).
  - The knowledge base's review pages describe the stages, personas, verification and feedback dataset as they run, and every `devops review` example in them parses: `devops ai review patch`, `--provider`, `--model`, `--orchestration-shape` and `--post-pr` are gone (#952).
  - `CONTEXT.md` defines a mitigated verdict as a defect a named guard in named files limits, as the verifier does, and adds unverified (#952).
- **`devops review` Help Says What the Options Do**:
  - `--persona` and `--all` name the personas each runs, `--summary` says it has no effect, `findings --invalidated` says findings.json holds only the findings a later verdict invalidated, and `export-feedback` names its reader and its default status. `docs/commands/review.md`, `docs/commands/ai.md`, `docs/CLI_REFERENCE.md` and the README are regenerated (#952).
- **`--secret` Is `--secret-name` (`devops ai runs connect`)**:
  - The option names the Kubernetes Secret that holds the run index's Valkey password, not the password, and is now called what `devops k8s enable-tls` and `devops tls enable-k8s` call theirs. `--secret` is gone without an alias (#956).
- **`OTEL_EXPORTER_OTLP_ENDPOINT` Is Only the Fallback (`devops_cli.telemetry.tracer`, `telemetry.endpoint`)**:
  - `telemetry.endpoint` is unset by default. The collector is `DEVOPS_CLI_TELEMETRY_ENDPOINT`, else the configured `telemetry.endpoint`, else OpenTelemetry's own `OTEL_EXPORTER_OTLP_ENDPOINT`, else `http://localhost:4318`. `OTEL_EXPORTER_OTLP_ENDPOINT` used to override the configuration files (#956).
  - Every command that saved the configuration wrote the built-in `telemetry.endpoint: http://localhost:4318` into the file, and saves no longer do. A file saved before this change still names that endpoint, which now outranks `OTEL_EXPORTER_OTLP_ENDPOINT`. To let the variable choose the collector, delete the line or set `DEVOPS_CLI_TELEMETRY_ENDPOINT` (#956).
- **`devops ai ast parse --query` Queries Only Files in a Known Language (`devops ai ast parse`)**:
  - A file whose extension names no supported language was queried as Python. It now exits 1 with the error a plain parse gives (#959).
- **The `--level` Help Promises No Token Budget (`devops ai read`)**:
  - The help described Level 0 as "<200 tokens", a figure only the guessed count supported. It now lists what the topology holds: classes, functions, exports and hotspots (#959).
- **Review Data Has One Place for Every Command: the Main Worktree in devops-cli's Own Repository, `~/.local/share/devops-cli` From Any Other (`devops ai ingest`, `devops ai prompt-eval`, `devops ai runs`, `devops ai cost`, `devops pr check-readiness`, `devops dashboard`)**:
  - What a review keeps, its sessions, history and baselines, the hallucination catalog, the mitigations ledger, the feedback dataset, runs, samples, library contracts and AI spend, resolves a relative data directory in one place whichever command reads or writes it (`resolve_review_data_path`): under the main worktree in devops-cli's own repository, as before, and under `~/.local/share/devops-cli` from any other repository, so it is in `~/.local/share/devops-cli/.data` there by default. A review started in another repository keeps it there (#972), and the commands that share it would have resolved it under the repository they ran in: the dashboard, `devops ai prompt-eval`, `devops ai runs`, `devops ai cost` and the mitigations perimeter check of `devops pr check-readiness` would have found no session, verdict, run, spend or mitigation such a review recorded (#972).
  - Library contracts are `libraries/` under that data directory, where each command used `.data/libraries` relative to the working directory, so a contract `devops ai ingest library` wrote in one directory reached no review started in another (#972).
  - `devops ai prompt-eval --dataset` resolves a relative path where review data is kept, as `data.feedback_dataset_path` does (#972).
  - Outside devops-cli's own repository, review data a repository's `.data` already holds stays there and is no longer read. Move it into `~/.local/share/devops-cli/.data` to keep it, or set an absolute `DEVOPS_CLI_DATA_DIR` naming that `.data`, which every command then uses for all of its data. Other data, such as the analysis cache, the CI cache, logs and sandboxes, still resolves under the main worktree outside a review (#972).
- **The Code and Docs Collections Are Searched at Once (`devops_cli.ai.rag.retriever`)**:
  - `SemanticRetriever.search` queries its target collections in parallel, so a query waits for the slower search, not both one after the other. The points are pooled in the collections' order, not the order the replies come back in, so the results, their order, which duplicate is kept and the fused scores are the same as before. A collection whose search fails still adds no points. The first collection is searched on the calling thread and the others on daemon threads that carry the trace context, so each `ai.rag.qdrant_search` span stays under `ai.rag.search`. They are joined before the search returns, except after Ctrl-C, which still stops a query such as `devops ai rag query` at once, and lets the process exit, rather than waiting out a stalled search's retries (#975).
- **The Qdrant Request Timeout Is a Setting, 300 s by Default (`devops_cli.config.settings`, `devops_cli.ai.rag.qdrant`)**:
  - `qdrant.timeout` (`DEVOPS_CLI_QDRANT_TIMEOUT`) sets how many seconds each Qdrant request waits per attempt. It defaults to 300 s, since 60 s is too short for a homelab Qdrant search and 300 to 600 s suits one, and must be greater than 0. `QdrantClient` defaulted to `DEFAULT_HTTP_TIMEOUT_SECONDS`, one hour per request, and no caller set a timeout, so a stalled search could hold a RAG query for an hour per attempt (#975).
  - Every place that builds the client passes the setting: review investigation, the `rag_search` tool, `devops ai rag query` and indexing. Indexing's upserts and deletes go through the same client, so they wait the same time per attempt. A timed-out request is retried after a reconnect, as before, up to 3 attempts (#975).
  - The client uses the timeout as given. A floor of 60 s no longer raises a smaller value, and a fraction of a second is sent to the Qdrant client rounded up to whole seconds, not down to 0 (#975).
- **Review Terminal Output Lists What Matters and Summarizes the Rest (`devops review path|branch|pr`, `devops_cli.ai.review.pipeline`)**:
  - The findings table lists CRITICAL, HIGH and MEDIUM findings, each under its number in `review.md`, and detail panels follow for CRITICAL and HIGH only. LOW and INFO findings are one line that counts them by status and gives the path to `review.md` and the command that lists them, such as `devops review findings <session> --severity LOW --details` (#987).
  - Dependencies are one line: packages scanned, vulnerable by severity, and not checked, pointing at the report's "External Dependencies" section. A table follows only for vulnerable packages (#987).
  - Network references are one line: references found, local and external, and flagged by reputation, pointing at the report's "Network References & Endpoints" section. A table follows only for flagged endpoints (#987).
  - The closing line names the session directory and `review.md`. `review.md` and `findings.json` are unchanged (#987).
  - Rendered from saved sessions at 120 columns, the branch review `20261002-180320` (126 findings, 58 dependencies, 162 network references) prints 1,731 lines instead of 3,469, and the path review `20261001-224227` (563 findings, 58 dependencies, 531 network references) prints 9,043 instead of 15,708. The detail panels of CRITICAL and HIGH findings make up most of what remains (#987).
- **Every Ollama Tier Keeps One Model Loaded and Serves One Request at a Time (`k8s/llm/profiles/ollama-profiles.yaml`)**:
  - All nine Ollama DaemonSets set `OLLAMA_MAX_LOADED_MODELS` and `OLLAMA_NUM_PARALLEL` to `1`. Ollama reserves KV cache for `OLLAMA_CONTEXT_LENGTH` × `OLLAMA_NUM_PARALLEL` tokens, so a tier now holds one context instead of two or four. In review session `20261003-051015`, gemma4:31b on ollama-48gib-slow reserved 512,000 tokens (4 × 128,000), put only 44 of its 61 layers on the GPU, and then failed to load; on ollama-64gib each call took 18 to 25 minutes, past the client's 1,200 s timeout (#1061).
  - Requests to a busy tier now queue in Ollama, and a tier that serves both an embedding model and a chat model, such as ollama-48gib-slow, unloads one to load the other (#1061).
- **The Project's Claude Code Settings Are Checked In (`.claude/settings.json`, `.gitignore`)**:
  - `.gitignore` ignored the whole `.claude/` directory, so the shared Claude Code settings (enabled plugins and permission rules) were never committed. It now ignores `.claude/*` and re-includes `.claude/settings.json`; personal settings (`.claude/settings.local.json`), `.claude/scratch/` and `.claude/worktrees/` stay ignored (#1087).

### Removed
- **`SpanHandle.record_llm_metrics` (`devops_cli.telemetry.tracer`)**:
  - Removed without a replacement. Nothing called it, and it wrote renamed and private keys beside the current ones. A reply's GenAI attributes are written by the `ai.llm.dispatch` span alone (#588).
- **Line-Based Stream Helpers (`devops_cli.ai.client`)**:
  - `_consume_streaming_lines`, `_read_response_lines`, `_extract_claude_stream_chunk`, `_extract_openai_stream_chunk`, `_extract_ollama_stream_chunk`, `_extract_ollama_stream_tuple` and `_extract_stream_chunk` are replaced by `_read_event_stream`, `_read_ndjson_stream` and one frame parser per provider in `devops_cli.ai.client.streaming`. The five that `devops_cli.ai.client` re-exported are removed from it, with no alias (#599).
- **ROADMAP-to-GitHub Sync (`devops gh issues sync-roadmap`, `devops gh issues reconcile-roadmap`, `devops gh milestones sync`, `devops release epic`)**:
  - Removed without shims, with `github/roadmap_sync.py`, `github/release_epics.py`, `--create-release-epics`, the ROADMAP-heading milestone extraction and the MCP tools `gh_sync_roadmap`, `gh_issue_reconcile_roadmap`, `gh_milestone_sync` and `release_epic_sync`. GitHub is the roadmap's source of truth, so nothing pushes `docs/ROADMAP.md` to it any more (#739).
- **pytest, rg and file Are No Longer Criteria Commands (`devops review path|branch|pr`, `devops_cli.config.constants`, `devops_cli.ai.review.review_environment`)**:
  - `CONST_ALLOWED_CRITERIA_BINARIES` drops `pytest`, `rg` and `file`. A criterion naming one is kept as a sentence and never run. A passing existing test shows no defect, and none of the three was on the sandbox's PATH: all 11 pytest criterion runs in the saved review sessions had failed with `bwrap: execvp pytest` (#847).
  - pytest is refused in the forms the validator reads too: `python -m pytest` or `python -m _pytest` (or one of their submodules); a `python -c` script that imports `main` or `console_main` from `pytest` or `_pytest`, or reaches either through a name it imports them as or through `__import__('pytest')` or `importlib.import_module` of a pytest module's name; and `find -exec pytest`, since `find` may no longer run commands (see Fixed). Under the repository's interpreter and the 30 s python limit they would run the project's real tests, and a `pytest.main` whose return value is discarded exits 0 whatever the tests do, even for a test file that does not exist. A criterion may still import pytest, for `pytest.raises` or a test module that imports it. A script that names the runner only at run time, as in `getattr(pytest, 'main')` or `runpy.run_module('pytest', run_name='__main__')`, still passes the validator and runs the tests (#847).
  - A pytest criterion settles no verdict, whatever its form: one the validator refuses stays a sentence, and the evidence rule counts only a `python -c` script that asserts over the cited code or calls the cited test directly (#847).
  - The review prompts (`ai/tasks/review.md`, `ai/tasks/review_output_instruction.md`) describe an executable criterion as a `python -c` command only, and so does `docs/SELF_IMPROVEMENT.md` (#847).
- **The Deterministic Embedding Fallback (`devops_cli.ai.rag.embeddings`)**:
  - `EmbeddingsEngine._deterministic_fallback`, `EmbeddingVector` and `EmbeddingList` are removed without a replacement. Embeddings come from a model or raise `EmbeddingsError` (#945).
- **`devops ai benchmark --suite` and `--dataset`, the MCP `benchmark_suite` Tool and `devops_cli.ai.benchmark.suite`**:
  - The suite sent empty prompts, from `benchmark_suite_system.md` and `benchmark_suite_user.md`, which never existed, scored the fix as the code under test and counted UNVERIFIED findings as not vulnerable. Its models (`BenchmarkSuiteCase`, `BenchmarkSuiteEvaluation`, `ModelSuiteMetrics`, `BenchmarkSuiteReport`), its leaderboard table and `--type suite` go with it; #413's corpus arms (`devops review corpus score`) replace it. A test now fails when a prompt file the code loads by name does not exist (#950).
- **Unused Review Prompts (`devops_cli.ai.tasks`)**:
  - `diff_review_prompt.md` and `review_pipeline_eval.md` are deleted. Nothing loaded them, yet they changed the prompt digest (#951).
- **The Single-Ollama Manifests (`k8s/llm/ollama-host-service.yaml`, `k8s/llm/values-ollama.yaml`)**:
  - `ollama-host-service.yaml` bridged an `ollama` Service to Ollama on the minikube host, and `values-ollama.yaml` held values for the `ollama/ollama` chart. Nothing has applied either since the in-cluster Ollama tiers replaced them. Both are deleted without a replacement, and `k8s/README.md` port-forwards `svc/ollama-16gib` for the Ollama API instead of `minikube service ollama` (#953).
- **The `ollama.llm.svc.cluster.local` Name in the Homelab Certificate (`devops tls homelab`, `devops tls enable-k8s`, `devops k8s enable-tls`)**:
  - The homelab TLS bundle no longer lists `ollama.llm.svc.cluster.local`, a Service nothing deploys. `*.llm.svc.cluster.local` still covers the Ollama tiers (#953).
- **Unregistered Telemetry Variables (`DEVOPS_TELEMETRY_ENABLED`, `DEVOPS_OTEL_ENDPOINT`, `DEVOPS_CLI_OTEL_ENDPOINT`)**:
  - The tracer read these three names, which no documentation listed, ahead of the configuration. They are gone without a shim; use `DEVOPS_CLI_TELEMETRY_ENABLED` and `DEVOPS_CLI_TELEMETRY_ENDPOINT`. The `devops telemetry profile` error names the new variable (#956).
- **Nested Settings Variables (`devops_cli.config.settings.Settings`)**:
  - `Settings` no longer reads `DEVOPS_CLI_<SECTION>__<FIELD>`. `load_settings()` never applied that form, so `DEVOPS_CLI_TELEMETRY__ENABLED=false` left telemetry on, but a bare `Settings()`, which builds the configuration reference and the API's `/config` answer, did read it (#956).
- **`NVDClient` (`devops_cli.security`, `devops_cli.security.vulnerability_lookup`)**:
  - `NVDClient` and its record parser are deleted with their export and test. Nothing called them (#956).
- **Dead Scanner Helpers (`devops_cli.security.semgrep`, `devops_cli.security.bandit`)**:
  - `_execute_and_parse_semgrep` and `_execute_bandit_subprocess` are removed without a replacement, with the imports and loggers only they used. Nothing called them; both scanners run through `BaseSecurityScanner`. A hygiene test fails on any module-level private function in `security/*.py` that nothing in `src/` or `tests/` references (#957).
- **Per-Layer Wasted Bytes (`devops docker analyze-layers`, `DiveLayerInfo`)**:
  - Dive's export has no per-layer wasted bytes, so `DiveLayerInfo.wasted_bytes` and the layer table's `Wasted (MB)` column were always 0. Both are removed. The image's wasted bytes stay in the summary line and in `--json` (#957).
- **The MCP Sampling Model Stub (`devops_cli.ai.agents`)**:
  - `MCPSamplingModel` is removed without a replacement, with its exports from `devops_cli.ai.agents` and `devops_cli.ai.agents.pydantic_agent`. It called the MCP SDK's async `ServerSession.create_message` without awaiting it, so a real session's completion was the text of a coroutine object, and a failed call, or no session, returned the fixed text `MCP sampling response generated via client session callback.` as if a model had written it. No command built it. `PydanticAgent.set_mcp_sampling_model`, which sets an `MCPToolset`'s sampling model, stays (#958).
- **Unused OS Access and Tool Search Classes (`devops_cli.ai.harness`)**:
  - `MountDir`, `OSAccess` and the harness `ToolSearch` are removed with their module, `ai/harness/os_access.py`, and with their exports from `devops_cli.ai`, `devops_cli.ai.agents` and `devops_cli.ai.harness`. Deleting `CodeMode` (#947) left `MountDir` and `OSAccess` without a user, and only its own test used the harness `ToolSearch`. `devops_cli.ai.agents.ToolSearch` is pydantic-ai's capability and stays; `devops_cli.ai.ToolSearch`, which was the harness class, is gone (#958).
- **Dead Round-Robin State and Duplicate URL Policies (`devops_cli.ai.client`, `devops_cli.ai.providers.ollama`, `devops_cli.ai.rag.investigator`)**:
  - `LLMClient` no longer copies the round-robin index, locks, semaphores and active-request map of `devops_cli.ai.client.network` as class attributes, nor keeps `_ollama_url_index` and `_ollama_url_lock`. The index was copied once at import and never followed the module's (#960).
  - `read_limited_json` and `LLMClient._read_limited_json` are replaced by `request_limited_json`. `validate_base_url`'s `allow_loopback_for_local_tooling`, the Ollama provider's `_is_loopback_or_private_allowed` and `_validate_ollama_url`, and the investigator's second Qdrant URL check are replaced by `validate_configured_service_url` (#960).
- **The `embeddinggemma:300m` Gateway Groups and bge-m3 on ollama-16gib-fast (`k8s/llm/gateway/configmap.yaml`)**:
  - No Ollama or gateway log shows a request to `embeddinggemma:300m`, and devops-cli's defaults and docs do not use it. Both of its groups are deleted (#1064).
  - `bge-m3:latest` keeps one deployment, on ollama-48gib-slow. On ollama-16gib-fast, which keeps one model loaded and serves `devops-chat` and `devops-review`, an embedding would evict the chat or review model (#1064).

### Fixed
- **Run Setups Name the Model That Verified (`devops_cli.ai.run_store`)**:
  - A review's run setup resolves verification as reviews do, layered on the analysis task. With `ai.tasks.verification` unset, which is the default, it now records the analysis model and that group's pool for verification, not the base `ai.model`. Setups also record each task's `temperature` and `top_p`. This changes the setups that `devops review benchmark`, `devops review samples validate --review` and `devops review corpus score` record, so their fingerprints differ from earlier runs' (#413).
- **Loki Deletes Logs Once They Are 30 Days Old (`k8s/logging/loki-values.yaml`)**:
  - `compactor.retention_enabled` is on, with `compactor.delete_request_store: filesystem`, which Loki 3 requires before it starts with retention on. `limits_config.retention_period: 720h` was set, but only the compactor applies it, and only with retention on. Loki never deleted a chunk by age: its retention had never run, and chunks 12 days old were still stored while the period read 2 hours (#550).
- **The Docs Name What Enforces the Complexity Cap (`AGENTS.md`, `CONTRIBUTING.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`)**:
  - These four files said `devops scan complexity` and the architectural invariant tests enforced the cap of 10. They now say that Ruff `C901` enforces it through `uv run devops ci` and the pre-commit hook, and that a test keeps the number of functions carrying markers from growing. `AGENTS.md` adds that a function over the cap is decomposed, never suppressed, and that `test_the_complexity_cap_has_no_escape` rejects Ruff's own `ruff:` suppression comments and ignore files that hide a source (#586).
  - They also say that the `structural-invariants` hook and `test_no_excessive_nesting_in_src` enforce nesting, and that `devops scan complexity` reports a different, in-house count and does not gate (#586).
- **Reviews No Longer Use Another Run's Symbol Delta (`devops review`)**:
  - Pre-analysis kept symbol lists that another review or `devops ai analyze branch` had cached. Verification read the newest cached analysis, whichever run wrote it, and the summary added up that analysis when the reviewed files had no delta. A finding could be exempted for a symbol that a different branch removed. Now only the session's own delta counts (#593).
- **`devops ai analyze branch` Compares a Renamed File With Its Old Path (`devops ai analyze branch`)**:
  - A renamed file is analysed at its new path and compared with its old one at the merge base. The plain `--name-status` parser read `old.py<TAB>new.py` as one path that does not exist, so it recorded the file as deleted. A reused file's delta is now computed again, because the cached one may be against an older merge base (#593).
- **Cut Replies Are No Longer Cached (`devops_cli.ai.client`)**:
  - A reply that ended at its token cap (`length`), was filtered (`content_filter`) or failed (`error`) is returned but not stored in the response cache, so the next identical call reaches the provider instead of the cut reply for 7 days. Replies cached before this change expire as before, or go at once with `devops ai cache clear` (#599).
- **The Dispatch Span No Longer Says Every Reply Stopped (`devops_cli.ai.client`)**:
  - `gen_ai.response.finish_reasons` was hard-coded to `["stop"]` on every `ai.llm.dispatch` span (#599).
- **The Historical Baseline FP Rate Leaves Out the Session It Compares (`devops review`)**:
  - Corrects #434's "Historical Baseline FP Rate" column in review.md. It counted the session being compared, because findings.json is written before the report, and counted a re-reviewed subject once per session. Its history also read only the reported findings in findings.json, while the session side counted every finding raised. One earlier VERIFIED session with the current INVALIDATED session on disk read `50.0% (1/2)`, and two copies of the earlier session made it `25.0% (1/4)` (#607).
  - The baseline now leaves the current session out, counts each subject once and reads every finding each earlier session raised (candidates.json, or findings.json without one). A category shows figures once any counted earlier session has it, including on a first re-review, and a note under the table gives the earlier sessions counted and the repeats collapsed (#607).
- **Roadmap Store Listings Fail Closed (`devops_cli.roadmap.github_store`)**:
  - The GitHub adapter reads each REST listing (milestones, issues, an issue's events, comments and blocked-by links) a full page at a time and raises, naming the read and the page, when a page is not a JSON list. Through `api --paginate`, a page answered with exit 0 and a body that is not a list, such as a proxy's error page, ended the listing there, so a bad first page read as an empty listing and a later one as a short one, and a first run could record a release as holding no items (#740).
- **Editing a Milestone No Longer Closes It (`devops gh milestones edit`)**:
  - `edit` sends only the fields it is given. Before, `devops gh milestones edit v0.2.25 --description x` also sent `state=closed` whenever a GitHub token resolved, and closed the milestone (#768).
  - When GitHub can't be read, `devops gh milestones list` exits 1 and names the failed read, instead of printing "No milestones found" (#768).
- **A Mitigation Stands Only on Code the Reviewed Tree Holds (`devops review path|branch|pr`, `devops_cli.ai.review.verification`)**:
  - A model's MITIGATED verdict stays MITIGATED only when every perimeter file resolves inside the reviewed tree through `safe_resolve_subpath`, and an identifier its mechanism names (`_extract_code_symbols`) appears in a perimeter file or in the finding's own file. An absolute path, even to a file in the tree, a `../` escape, a symlink, a directory and a missing file are unresolved, and a pull request review's tree holds only the pull request's files. Otherwise the finding is UNVERIFIED, stays reported, drops the line the verdict cited, and its `verification_note` names the check that failed. The finding's own file is read where its location points, absolute as a scanner writes it or relative, so a mechanism held only there still counts. A HIGH "Command injection via os.system" finding that the verifier called mitigated by a "shlex.quote wrapper in safe_exec" in `src/does/not/exist.py`, citing line 999 of a four-line file, was MITIGATED with no note and the review recommended APPROVE; it is now UNVERIFIED with a `mitigation-unproven` note saying that `src/does/not/exist.py` does not resolve inside the reviewed tree, and the review requests changes (#845).
  - A documentation file, the conventions file `.devops/review.md` among them, is no perimeter, and a mechanism that negates itself ("caught but not logged", "does not fully sanitize", "is expected to handle", "intended to", "too permissive") describes the defect rather than what limits it. Replayed against session `20261001-224227`'s 28 MITIGATED verdicts, 26 become UNVERIFIED: 19 mechanisms name no code identifier, 5 describe the defect and 2 perimeters are `.devops/review.md`. The 2 naming `validate_service_url` and `is_relative_to()` in the files that hold them stay MITIGATED (#845).
  - A verdict that names no reason, mechanism or perimeter files says which, under the same note kind (#845).
- **A Confirmation Cites a Line Its File Has (`devops review path|branch|pr`, `devops_cli.ai.review.verification`)**:
  - A model's VERIFIED verdict whose `citation_line` is below 1 or past the end of the finding's file is UNVERIFIED, stays reported and drops the citation, with a `citation-out-of-range` note naming the line, the file and its length. A citation inside the file stays VERIFIED. A scanner's finding, located by an absolute path inside the reviewed tree, is checked the same way. Each verdict of a reply is checked on its own: a fabricated one leaves the others as they were (#845).
- **A Confirmation or Mitigation Its Own Reason Contradicts Is Not Applied (`devops review path|branch|pr`, `devops_cli.ai.review.verification`)**:
  - A model's VERIFIED or MITIGATED verdict whose reason denies the finding's claim is UNVERIFIED, stays reported and drops its citation, with a `verifier-contradiction` note quoting the denial. In review session `20261003-012555` qwen3-coder confirmed two Semgrep findings, "Untrusted user input in `importlib.import_module()`", with reasons ending "No user input reaches this point" and "These are not derived from untrusted user input", and #948's ranking put both among the report's top 8 rows; in session `20261003-005122` it called two of the same findings mitigated on the same grounds. The guard mirrors the self-refutation guard on the same claim words and negations: a negation followed by at least two consecutive words of the claim that the claim does not negate itself (#845).
  - A confirmation whose reason supports the claim is still applied, also when it negates a guard ("this does not prevent path traversal") or a word the claim negates too ("no input validation" against "Missing input validation"). Over 778 cached VERIFIED and MITIGATED verdicts, the plain mirror (any negation and 60% of the claim's words) would have set aside 318; this guard sets aside 13, 12 of which argue their finding away (#845).
  - A verdict whose reason says a criterion passed ("verified by the test execution which passes") when every recorded run of a criterion failed gets the same note. Session `20261003-005122` confirmed a finding that way while its criterion had failed with `No module named 'pytest'` (#845).
- **The Profile Counts Mitigations That Proved Nothing (`devops review path|branch|pr`, `devops_cli.ai.review_schema`)**:
  - `verdict_distributions.verification_note` in `profile.json` counts `mitigation-unproven`, `citation-out-of-range` and `verifier-contradiction` notes as their own kinds. A mitigation degraded for want of a mechanism or perimeter was noted in free text and counted as `other` (#845).
- **A Perimeter Path Matches Only Itself (`devops review branch|pr`, `devops pr check-readiness`, `devops_cli.ai.review.mitigations`)**:
  - The perimeter-change warning stripped paths with `.lstrip("./")`, which cut the dot off `.github/...` and `.devops/...` and the root off an absolute path, so a change to `github/workflows/ci.yml` warned about a mitigation whose perimeter is `.github/workflows/ci.yml`, and `etc/hostname` matched `/etc/hostname`. It now strips a leading `./` only. An absolute path inside the repository is read relative to its root, so a person's mitigation of a scanner finding, whose perimeter is the finding's absolute path, still warns when that file changes; an absolute path outside the repository matches only itself (#845).
- **A Verifier Reply Cut at Its Token Cap Settles No Verdict (`devops review`)**:
  - A verifier reply that ended at its token cap (finish reason `length`) no longer settles a verdict, even when JSON repair can close it. Every finding it was to judge stays unverified with the note `verifier-reply-cut`. In session `20261002-214641`, JSON repair closed a reply cut mid-reason into an INVALIDATED verdict on `ai/mcp/server.py:202`, whose reason ended "is therefore incorrect; the", and the finding left the report (#846).
- **What the Verifier Writes Reaches the Saved Finding (`devops review`)**:
  - The pipeline copies every field verification owns, listed once as `VERDICT_FIELDS` beside `apply_verdict`, from the verified finding back onto the saved one. Its own list of fields left out the severity, so a finding kept the reviewer's severity after the verifier rated it (#846).
  - Confidence is kept between 0 and 1 whenever a verdict is written. A command given as both a verification and an invalidation criterion was counted twice, and 3 findings of session `20261001-224227` carried a confidence of 2.0 (#846).
  - A reviewer's reply can no longer bring its own confidence, citation line, mitigating mechanism, perimeter files, regression test or criteria results. They are cleared on parsing with the rest of the verification state (#846).
- **Offline Tests (`tests/test_finding_repetition_compression.py`)**:
  - The monologue test no longer reads the local `.data` response cache (#846).
- **Criteria Run in the Reviewed Repository's Own Environment (`devops review path|branch|pr`, `devops_cli.sandbox.host`)**:
  - When the reviewed repository has a `.venv/bin`, the host sandbox puts it first on `PATH`, so `python` and `python3` are the repository's interpreter with its own dependencies and `ruff` is its ruff. The sandbox's `PATH` was `/usr/local/bin:/usr/bin:/bin`, so `python` was the system's Python, whose third-party modules came from the devops-cli install in `/usr/local/lib/python3.14/dist-packages`, and `ruff` was not found: all 6 ruff criterion runs in the saved review sessions had failed with `bwrap: execvp ruff`. A repository without a `.venv/bin`, or whose `.venv` links outside it, keeps the system `PATH` (#847).
  - A criterion that imports the reviewed project's test dependencies no longer fails on the import. In review session `20261002-214641` the invalidation criterion for `tests/test_security_bandit.py:142-154`, a `python -c` importing that test module and so pytest, failed with `No module named 'pytest'`; replayed through the sandbox it exits 0 (#847).
  - A virtualenv's `python` links to the interpreter it was made from. When that lies outside the sandbox's mounts, as uv's managed CPython under `~/.local/share/uv/python` does, the sandbox binds its installation read-only, or the link would dangle. The repository chooses where the link points, so the installation is bound only when it holds CPython's standard library (`lib/python3.*/os.py`), contains neither the home directory nor the repository, and has no `.ssh`, `.aws`, `.kube` or `.git` in its path. A virtualenv whose `python` cannot be bound, or links to nothing, is passed over and the system `PATH` stands (#847).
- **A Python Criterion Is `python -c <script>` or `python -m <module>` (`devops review path|branch|pr`, `devops_cli.ai.review.review_environment`, `devops_cli.ai.review.criteria_evidence`)**:
  - A python criterion is accepted only with `-c` or `-m` as its first argument; any other shape is refused and kept as a sentence. Python reads its own options up to the first `-c` or `-m`, inside a cluster such as `-Bc` too, and passes what follows to that script or module, but the validator and the evidence rule read the command otherwise. The evidence rule took the script after the first `-c` token wherever it stood, so `python -m this -c '<assert>'` and `python -Bc pass -c '<assert>'` exited 0 without running the assertion, and a failing assertion over the cited code settled VERIFIED with confidence 1.0, or as an invalidation criterion INVALIDATED. The validator looked for `-c` anywhere before it looked for `-m`, so `python -m socket -c pass` ran a forbidden module; and it missed a `-c` inside a cluster, so `python -Bc '<script>' -c pass` checked only `pass` and ran a script that imports `subprocess`. Both now read the command one way (`python_invocation`): the script or module Python runs is the one checked, and a `-c` after `-m` is the module's argument, which settles nothing. All 3,710 distinct python criteria in the saved review sessions have `-c` or `-m` first (#847).
  - `python -m` refuses a submodule of a forbidden module (`http.server`, `urllib.request`), as an import of one was already refused (#847).
  - A `find` criterion may only search: `-exec`, `-execdir`, `-ok`, `-okdir`, `-delete`, `-fprint`, `-fprint0`, `-fprintf` and `-fls` are refused. `-exec` ran any binary on the sandbox's `PATH`, allowlisted or not, and pytest among them once the repository's `.venv/bin` led it (#847).
- **A Scanner Reason With Brackets Prints as Written (`devops scan report`, `devops scan trivy|secrets|sast|iac`)**:
  - The "was not run" and "failed during execution" warnings read a scanner's reason as Rich markup. A reason with a closing tag such as `[/x]` stopped `devops scan report` with a `MarkupError` and exit code 1 after it had written the SARIF file. The reason now prints literally (#915).
- **Open PRs Into a Release Branch No Longer Conflict on `CHANGELOG.md` (`changelog.d/`, `devops release prepare`, `devops release changelog --update`)**:
  - Each PR's entry is its own `changelog.d/<issue>.md`. The cut merges every fragment into the version's section, categories in Keep a Changelog order and fragments in issue order within each, deletes them in the same run and leaves `## [Unreleased]` an empty heading. A misnamed file, text outside a category or an unknown category stops the cut before any write and names the file. A dry run lists the fragments and writes nothing, and with no fragments the section is written as before (#933).
- **Readiness Blocks a PR That Changes `CHANGELOG.md` or `docs/ROADMAP.md` (`devops pr check-readiness`)**:
  - A PR into a `release/*` branch that adds, modifies, renames or removes either file gets one blocker naming it and the fragment to add instead. Release-process PRs, `chore/open-vX.Y.Z` or `chore/cut-vX.Y.Z` optionally followed by `-<slug>` from the same repository into `release/vX.Y.Z`, are exempt from grounding as the release PR is (#933).
- **Reviews Ask an Unserved Embedding Model Once, Then Run Without RAG (`devops review`, `devops_cli.ai.rag.investigator`)**:
  - A review against a gateway whose backends serve only the review model asked for the embedding model on every RAG lookup: once per finding in verification, per file in the review payloads, in pre-analysis and per persona prompt. Every request failed and logged a warning, and on a node that keeps one model loaded each one could swap out the review model. Now the first lookup whose query cannot be embedded turns RAG off for the rest of the process. It logs one warning that names the model and the error, and says how to fix it: serve the model, point `ai.tasks.embedding` at a backend that serves it, or set `ai.rag.enabled: false`. Later lookups return no context without building a retriever or sending a request, and `clear_investigation_cache()` lifts the stop. Until the model has answered a lookup, lookups that run at once take turns, so the review workers' parallel per-file lookups (16 on a gateway) send one request between them rather than one each before the first failure comes back. Once the model answers, lookups run in parallel again. Five findings against a gateway that answers HTTP 400 now send one embedding request, not five, and four review workers looking up their files at once send one, not four (#945).
- **A Failed Embedding Raises Instead of Becoming a Hash Vector (`devops_cli.ai.rag.embeddings`, `devops_cli.ai.rag.retriever`)**:
  - `EmbeddingsEngine` turned four failures into a hash of the text: an HTTP error, an unreachable endpoint, a text every Ollama node refused, and a missing provider. Retrieval then searched Qdrant with that vector and could hand unrelated chunks to the verifier as context, and `devops ai rag index` and `devops ai ingest index-libraries` would have stored it. Each failure now raises `EmbeddingsError`. Its message names the model, each endpoint or node it asked, and the HTTP status with the start of the reply, or the error. `SemanticRetriever.search` and `retrieve_context` raise it rather than returning no results (#945).
  - These commands now print the error and exit 1 rather than show a traceback: `devops ai rag index`, `index-kb`, `query` and `drift --auto-sync`, and `devops ai ingest index-libraries` and `query-library`. Indexing stores no vector for a text the model did not embed. The agents' `rag_search` tool returns `RAG search unavailable: <error>. Fallback: use search_code.`, as it does when Qdrant is unreachable (#945).
  - When Ollama batches run in parallel, the first batch that every node refuses cancels the batches still queued, rather than sending them to the same nodes (#945).
- **A Change Made Only of Routed Files Calls No Model (`devops review branch|pr`)**:
  - A branch or pull request whose changed files were all lockfiles, planning documents or generated references paged into one empty page, which the legacy engine sent to the model. Such a review now calls no model, runs the secret scan on those files, writes its report and says that nothing was left for the personas, or, with the static scan off, that none of the files was read. Its findings.json names no persona (#948).
- **The Verifier Only Lowers a Severity (`devops_cli.ai.review.verification`, `devops_cli.ai.review.pipeline`)**:
  - A verifier reply could raise a finding's severity. It can now only lower it, the persona's value stays as `severity_raw`, and the pipeline keeps the lowered value, which its copy-back used to drop (#948).
- **Advisories Come From This Session's Scan (`devops_cli.ai.review.verification`, `devops_cli.ai.review_schema`)**:
  - A CVE or GHSA id stays in a finding's references only when a vulnerability record of this session's scan carries it, OSV's or one Trivy reported. Any other is removed and `reference_note` says which, and a finding left with no reference had it as its only evidence and is INVALIDATED as `deterministic:unbacked_advisory`. Session `20261001-224227` cited 11 CVEs from Log4j, polkit, Apache httpd, OpenSSH, axios and JUnit against a Python CLI whose 58 dependencies it had scanned clean (#948).
  - A record's aliases match too, and OSV's `aliases` are now kept on each record. The batch lookup a review makes returns ids only, so a review's records carry no alias yet, and a finding citing the CVE of a PYSEC or GHSA record the scan found is stripped (#948).
  - Verification checks a finding against every dependency the session scanned, whichever file declared it, and against the packages Trivy found vulnerable, which no longer count as scanned clean. Each file's verification passed none, so a claim against a dependency the scan found clean was never checked (#948).
  - A persona reply's `external_dependencies` and `network_references` are cleared when it is parsed, so no check trusts a dependency a model declares clean, and a finding's `severity_raw` and `reference_note`, which only the pipeline writes, are cleared whether the reply was parsed from text or by the agent framework (#948).
  - The placeholder check also catches ids of ascending digits such as `CVE-2023-1234`, not only `x`, `n` and `?` runs, unless this session's scan carries the id: sequential ids are published ones too, `CVE-2016-1234` (glibc) and `CVE-2023-1234` (Chrome) among them, and Trivy's own finding of one must stand (#948).
- **Verdicts Given at Once (`devops review verify`, MCP `verify_finding`)**:
  - Verdicts given on one session at the same time, as an MCP client's parallel calls give them, take turns under a lock on the session (`.verify.lock`). Each call read the session's files before another wrote them and wrote over that verdict, though every call reported success (#949).
  - A verdict whose session files cannot be written is not recorded: files already written are put back, each learned-catalog or ledger entry it updated is put back as it was, every field included, each it created is removed, and the command exits 1. A reset withdraws the entries it released only once the files are written (#949).
- **Resets Undo Their Side Effects (`devops review verify --status UNVERIFIED`)**:
  - A finding records one id for each learned-catalog or mitigations-ledger entry a person's verdicts on it created or added to (`learned_catalog_ids`, `mitigation_ledger_ids` in findings.json). Resetting it to UNVERIFIED withdraws each: an entry another verdict also recorded loses one count (`occurrence_count` in the catalog, the new `verdict_count` in the ledger) and stays, and one nothing else recorded is removed. Every other entry is left alone (#949).
- **Feedback Records Are Not Human by Default (`devops_cli.ai.review.exporter`)**:
  - `FeedbackRecord.verified_by` defaults to `unknown`, not `human`, so the export labels a record `human` only when a person judged the finding (#949).
- **One Settings Load per Review (`devops review path`, `branch`, `pr`)**:
  - Each command loads the configuration once; it loaded it twice (#949).
- **Machine-Learned Catalog Entries Are Purged (`devops review`)**:
  - The first load of the learned catalog removes every entry the review's own checks taught it, and logs once how many. In session `20261001-224227` its 35 entries were all `general`, with signatures pairing common words such as `exception` and `handling`; had their ground truth ever passed, they would have invalidated 240 of that session's 903 candidates, 19 VERIFIED HIGH findings among them (#950).
- **The Harness Planning and Playwright Guidance Load From Their Prompt Files (`devops_cli.ai.harness`)**:
  - `planning_guidance.md` and `playwright_guidance.md` did not exist, so the exported `DEFAULT_PLANNING_GUIDANCE` and `DEFAULT_PLAYWRIGHT_GUIDANCE` held inline fallbacks that differed from the guidance the capabilities used. Both prompts are now files, and the capabilities and the exports read the same text (#950).
- **Port-Forward Reaches the Ollama Tier (`devops k8s port-forward`, `devops k8s configure-urls`)**:
  - `devops k8s port-forward --stack llm` forwarded `svc/ollama`, which nothing has deployed since the Ollama tiers replaced the single workload, so the Ollama forward failed. It now forwards `svc/ollama-16gib`, the default tier's Service, on port 11434 (#953).
  - `devops k8s configure-urls --stack llm` looks up `ollama-16gib` instead of the missing `ollama` Service. It still detects no cluster address for Ollama, because the tier's Service is ClusterIP, with no NodePort or load balancer. As before, it sets `ai.ollama_urls` to `http://localhost:11434` only while something answers there, which the forward above now can (#953).
- **Failover to Ollama Reaches a Deployed Service (`devops ai gateway failover`, `devops_cli.ai.gateway`)**:
  - `devops-chat` and `devops-embedding` failed over to `ollama.llm.svc.cluster.local`, which nothing deploys. They now fail over to the default Ollama tier, the same `ollama-16gib` Service their default routes use (#953).
- **Portkey's Ollama Egress Selects the Ollama Tiers (`k8s/llm/portkey/networkpolicy.yaml`)**:
  - The rule selected `app.kubernetes.io/name: ollama`, which no deployed pod carries. It now selects `llm.devops.io/provider: ollama`, which every tier carries, on port 11434 (#953).
- **A Failed Embedding Fails the Model Instead of Scoring It (`devops ai benchmark --type embedding`, `devops_cli.ai.benchmark.embedding_runner`)**:
  - A model whose embedding requests failed, on an unreachable server or one that does not serve it, was scored anyway. With every request failing it printed `✓ ... → 35.0%`: a p50 latency of 0.0 earned full latency points, and the recommendations named it the lowest-latency model and, at dimension 0, the most memory-efficient. Now the first failed request ends the model's run and no later request is sent. The run prints `✗ <model> on <server> | <error>`, and its result has `failed: true`, the error cut to 256 characters, the latencies of the requests that succeeded before it, or null, and no scores (#954).
  - A failed run ranks after every scored one, with no medal, `-` for each metric and `failed` for the score, and the Markdown report lists each with its error under "Failed Runs". The server summaries and the recommendations count only scored runs (#954).
  - A server the benchmark refuses to reach, or a run that raises anything else, is reported failed rather than dropped from the report with only a log line (#954).
  - In the report JSON, `latency_ms_p50`, `latency_ms_p95` and a server's `avg_latency_p50_ms` are null rather than 0.0 when no request was timed (#954).
- **Registry and Build Text Prints As Written (`devops docker push`, `devops docker build`)**:
  - A push status or error from the registry, and each line of build output, was read as Rich markup. An error such as `denied: [/v2/repo] access` ended `docker push` in a `MarkupError` traceback instead of the error and exit 1, `[internal]` vanished from a line, and `[link=...]` text became a terminal link. The text now prints as written, and control characters are still stripped (#955).
- **Scraped Metrics Print As Written (`devops sandbox metrics`)**:
  - Label values and `# TYPE` text from the scraped endpoint were read as Rich markup in the metrics table, so a label value such as `[/]` ended the command in a `MarkupError` traceback, and others could add styles or links. The metric name, type and labels are now shown as written. The label string is still cut to 40 characters, before it is escaped, so the cut never lands inside an escape. The target in the table titles is shown as written too (#955).
  - A `# TYPE` line counts only when it names a metric and gives a type the Prometheus text format defines: `counter`, `gauge`, `histogram`, `summary` or `untyped`, in any case. Any other line is ignored, and the samples' type is inferred from their name, in the table and in `--json`, as for a metric with no `# TYPE` line. That includes the OpenMetrics-only types, such as `info` and `stateset` (#955).
  - The scrape error carries the HTTP client's exception text, which can quote the endpoint's own bytes, as h11's `illegal header line` does. It prints as written in the `SCRAPE WARNING` line and the error line, and the target prints as written in the healthy and threshold-exceeded lines too (#955).
- **The CLI Reference Shows Defaults That Cannot Be Credentials (`devops docs generate`, `devops_cli.docs.generator`)**:
  - A default was masked whenever a credential keyword appeared anywhere in the option's name or envvar, so `--max-tokens` (TOKEN), `--valkey-port` (vaLKEY), `--key-size`, `--max-tokens-increase`, the TLS key path and two Kubernetes Secret names showed `<masked>`. The reference now shows `1500`, `200`, `0.2`, `6379`, `2048`, the path, `homelab-tls` and `valkey-runs-auth` (#956).
  - A text default is masked when the option's name or envvar names a credential, matched word by word: TOKEN, SECRET, PASSWORD, PASSPHRASE, CREDENTIAL, AUTH or APIKEY, or API followed by KEY. A name that ends in NAME holds what a credential is called, so `--secret-name` is shown. A number, a boolean or a path is never masked. An option that hides its input, Click's own marker for a secret, is always masked (#956).
- **An Off Switch Reads as an Off Switch (`devops docs generate`, `devops_cli.docs.generator`)**:
  - The reference listed a boolean's off switch among its aliases, as in `--rootless`, `--root`, although `--root` turns the host UID/GID mapping off. Off switches now follow a slash, as in `--rootless` / `--root` and `--follow`, `-f` / `--no-follow` (#956).
- **A Failed OSV Lookup Is Not a Clean Package (`scan_osv`, the `security_intel_package` tool, `devops scan fix --package`, `devops_cli.security.vulnerability_lookup`)**:
  - `OSVClient.query_package` returns a `PackageLookupResult`, as `query_batch` does, and a failed lookup carries its `reason`: OSV's status code or the request's error, capped at 256 characters. `scan_osv` answers `OSV lookup failed: <reason>` instead of `No known vulnerabilities found`, and `devops scan fix --package <name>` stops with the reason instead of planning nothing (#956).
- **Nothing Claims an NVD Lookup (`security_intel_package`, `scan_osv`, `devops ai review`, `docs/cheatsheets/security_and_ssh.md`)**:
  - devops-cli queries OSV.dev for package advisories and never NVD. The tool descriptions, `scan_osv`'s reply, the review report's dependency heading and console tables, the security cheatsheet and the code review manual no longer say it queries NVD (#956).
- **The `k8s_pods` Tool Lists the Namespace It Is Given (`k8s_pods`, `devops_cli.ai.mcp.server`)**:
  - The tool validated its `namespace` and then ran `devops k8s status`, which ignored it. It runs `devops k8s pods -n <namespace>`, or `devops k8s pods -A` when the namespace is empty (#956).
- **Knowledge-Base Examples Import Names That Exist (`devops_cli/libraries/fastmcp.md`, `devops_cli/libraries/pydantic_ai.md`)**:
  - The FastMCP manual's tool example imported `pods` from `devops_cli.commands.k8s`, which has no such name, and returned a canned string. It now shows the real `k8s_pods` tool, and the manual says tools run the `devops` CLI through `_run_mcp_cmd`. The Pydantic AI manual's example no longer imports `Finding` from `devops_cli.models.review`, a module that does not exist. A test fails on any `devops_cli` import in a knowledge-base Python example that does not resolve (#956).
- **One Section per Cadence Letter (`docs/ROUTINE_TASKS.md`)**:
  - The final pre-commit stage was a second `Cadence B`. It is now `Cadence A (final stage)`, so B, C, D and E keep naming what task files cite them for (#956).
- **Dive Layer Analysis Says When There Is None (`devops docker analyze-layers`, the `docker_analyze_layers` tool, `devops_cli.security.dive`)**:
  - Without a `dive` on PATH, or with one that is a symlink, `run_dive_analysis` returned a made-up analysis for any image: 98% efficient, 150 MB, and two layers, `FROM python:3.14-slim` and a `COPY` of uv. Any dive error returned a 100% efficient image of 0 bytes. The result now has a `status`, `ran`, `unavailable` or `failed`, and a `reason`, and only a `ran` result carries measurements (#957).
  - `analyze-layers` prints `Dive layer analysis unavailable: <reason>` (or `failed: <reason>`) as a warning and exits 1 when dive did not run. `--json` prints the result with its `status` and `reason` and also exits 1. The `docker_analyze_layers` tool answers `Dive not available: <reason>` or `Dive analysis failed: <reason>` instead of an efficiency score (#957).
  - With `--json`, stdout holds only the JSON document. The `Analyzing container image layers ...` line came first and made it invalid JSON (#957).
  - Each layer command in the table is shown as written. Commands come from the image's history, which whoever built the image controls, and they were read as Rich markup: `pip install uvicorn[standard]` showed as `pip install uvicorn`, and a command could add styles or terminal links (#957).
  - Dive runs as `dive <image> --json <file>`, with the file in a private temporary directory, and that file is read. `--json -` made dive write a file named `-` into the working directory while the code parsed dive's progress text on stdout. The export is read by the keys dive writes: `image.efficiencyScore`, `image.inefficientBytes`, `image.sizeBytes`, and each layer's `index`, `digestId`, `sizeBytes` and `command`. The `devops scan` dive adapter runs dive the same way, so an inefficient image is a finding there instead of an empty run (#957).
- **`devops k8s rbac-audit` Audits the Cluster (`devops k8s rbac-audit`, `devops_cli.k8s.rbac`)**:
  - The command made no cluster call and always printed one fixed `PASS` row. It now reads `kubectl get clusterrolebindings,rolebindings -o json` and `kubectl get clusterroles,roles -o json`, with `--all-namespaces`, or `-n <namespace>` when `--namespace` is given. It lists each subject that a binding grants the built-in `cluster-admin`, `admin` or `edit` ClusterRole, or a role with `*` in its verbs, resources or API groups. ServiceAccounts in `kube-system` and `system:` users and groups are cluster components and pass, except `system:anonymous`, `system:unauthenticated`, `system:authenticated` and `system:serviceaccounts`, which stand for every client or every service account. A user named `system:serviceaccount:<ns>:<name>` or a group named `system:serviceaccounts:<ns>` is that namespace's ServiceAccounts and passes only in `kube-system`. The control-plane grants that k3s and kubeadm make on every cluster pass too, so a fresh cluster passes: users `kube-apiserver` and `k3s-cloud-controller-manager` (k3s) and group `kubeadm:cluster-admins` (kubeadm 1.29+). Names read from the cluster are shown literally, not as markup (#957).
  - It exits 1 when it finds a violation, and when kubectl cannot read the objects, showing kubectl's error. A clean cluster prints how many bindings it audited. `--namespace` has help text (#957).
- **Checkov's Built-In Fallback Finds the `latest` Base Images and Privileged Containers It Missed (`devops scan`, `devops_cli.security.checkov`)**:
  - Dockerfiles: a `FROM` with flags, such as `FROM --platform=$BUILDPLATFORM python:latest AS build`, and an untagged `FROM alpine` are flagged as pulling `latest`. A digest pins either. `scratch` and an earlier stage's name are skipped. `USER` is matched in any case, so `user nobody` no longer reports a container running as root (#957).
  - Dockerfiles are read as Docker reads them. A line ending in `\`, or in the character a `# escape=` directive sets, continues on the next line. The body of a BuildKit heredoc (`RUN python3 - <<EOF` up to `EOF`) is not read as instructions. A continued `FROM` or `USER` is found. Lines in a heredoc are never taken for instructions: a Python `from pathlib import Path` there is not a base image, and an nginx `user nginx;` is not a `USER` (#957).
  - A `$ARG` in an image skips the check only where it can hide the tag or digest, as in `python:${TAG}` or `$BASE`. `${REGISTRY}/library/python:latest` and an untagged `${REGISTRY}/python` are flagged (#957).
  - Kubernetes YAML: each document's pod spec is read wherever its kind keeps it (`spec`, `template.spec`, `spec.template.spec`, `spec.jobTemplate.spec.template.spec`), with its `containers`, `initContainers` and `ephemeralContainers`. The resources in a `List`'s `items`, which is what `kubectl get -o yaml` writes, and in an OpenShift Template's `objects` are read the same way. A privileged DaemonSet, StatefulSet, Job or CronJob is found, and `privileged: True`, `yes` or `on` counts. A file that does not parse as YAML, such as a Helm template, is matched line by line. So is YAML nested too deep to parse; it does not stop the scan. Manifests are parsed with libyaml when PyYAML has it, which keeps large CRD bundles fast. Checkov is not installed in the devcontainer or CI, so this fallback is what `devops scan` runs there (#957).
  - Each resource is walked once, so YAML anchors fanned out through a `List`'s `items` cannot make the scan run for hours, and a file nested deeper than the parser can follow is checked line by line (#957).
- **`devops scan complexity` Measures a Function Defined Directly in Another on Its Own (`devops_cli.security.complexity`)**:
  - A `def` or `class` written directly in a function body was walked as part of that function: its branches and depth counted toward the enclosing function, and it was never reported. Nested functions and classes are now measured on their own wherever they appear. The methods of a class defined in a function are methods, and a function nested in a method is not one (#957).
- **Toolset Instructions Reach the Agent's Run Prompt (`devops_cli.ai.agents`)**:
  - `PydanticAgent.run`, `run_sync`, `run_async` and `iter` build their system prompt with a `RunContext`. Given one, a devops-cli `FunctionToolset` or `AbstractToolset` answered with a coroutine that was closed unread, so its instructions were missing from the prompt of every run while `run_stream`, which passes no context, had them. pydantic-ai's own toolsets were missing with or without a context. A devops-cli `AbstractToolset` is now asked for its instructions synchronously. Any `FunctionToolset`, devops-cli's or pydantic-ai's, gets the run's context and its coroutine is run to completion, so its dynamic instructions render too (#958).
  - Inside a running event loop the coroutine cannot be run from synchronous code. A devops-cli `FunctionToolset` then gives its static instructions, and each dynamic one it leaves out is logged at debug level. A pydantic-ai toolset's instructions are skipped with a debug log record naming the toolset, and a toolset that raises is logged as a warning. All of these were dropped silently (#958).
- **Deferred Tool Hooks Get the Run's Context (`devops_cli.ai.agents`)**:
  - A `HandleDeferredToolCalls` handler taking `(ctx, requests)` was called with the requests alone during a run, which then ended with a `TypeError`. The loop now passes its `RunContext`. The call is chosen by the handler's signature alone: a handler that can be called with the requests alone, such as `(requests)` or `(requests, **kwargs)`, gets them alone, and any other gets `(ctx, requests)`, with a fresh `RunContext` when it is called without one (#958).
  - Every capability inherits pydantic-ai's async `handle_deferred_tool_calls(ctx, *, requests)`, and the loop called it with the requests alone. A run with any other capability, such as `Thinking`, ahead of the handler, or with no handler at all, ended with a `TypeError` once a tool needed approval. Only a capability that overrides the hook is asked, with the run's context, and its coroutine is run to completion. A capability's own `handle_deferred` method gets the context when it can take a second positional argument (#958).
  - Inside a running event loop an async hook cannot be run from synchronous code. The lookup then stops with a warning naming the capability, and the requests go back to the caller as `DeferredToolRequests`, so no capability after it, such as an approving `HandleDeferredToolCalls`, decides in its place (#958).
- **SQLite Memory Keeps What It Writes (`devops_cli.ai.harness.SqliteMemoryStore`)**:
  - The store opens a connection per call and defaulted to `:memory:`, which gives each connection a new empty database: a write reported `ok` and the next read returned nothing. `database` is now required, takes a `str` or a `Path`, and refuses `:memory:` and the empty name, which does the same with a temporary file. `InMemoryStore` keeps memory for the life of the process (#958).
- **Stopping a Background Command Ends Its Whole Process Group (`devops_cli.ai.harness.Shell`)**:
  - `stop_command` found the group through the leader's pid, which fails once the leader has exited and been reaped, and swallowed the error, so the leader's children kept running while it reported the command terminated. It also sent SIGKILL only when the leader outlived SIGTERM, so a child ignoring SIGTERM kept running. The group is now signalled by its id, which is the leader's pid, and probed until no member is left, and the members still there when the grace period ends get SIGKILL. The grace period is `Shell(stop_grace_seconds=...)`, 3 s by default. A group it may not signal, and a leader that outlives SIGKILL, are logged as warnings (#958).
- **Polyglot Outlines Parse With Tree-Sitter (`devops ai read --inspect`, MCP `ai_read`, `devops_cli.ai.inspection`)**:
  - The outlines of every non-Python file, at all three levels, came from the regex fallback alone and never from the tree-sitter grammars the project ships. That included a Python file that does not compile. They now come from one `TreeSitterEngine.parse_code` parse, which still falls back to the regex parser when a grammar finds nothing. Take a Rust file declaring `pub fn plain(x: i32)`, `pub fn process<T: Clone>(x: T) -> T`, `pub const fn c()` and `unsafe fn u()`. Its outline listed only `plain`, and `--symbol process` showed lines 1-4 of the file without saying the symbol was not found. All four functions are now listed, and `--symbol process` shows its own line (#959).
  - A Level 1 skeleton line for a TypeScript, Go, Rust or Java function held only its parameter list, `(x: string, y: number)`, with no name or return type. It is now the declaration line, `export function a(x: string, y: number): Promise<void> {}` (#959).
  - Level 0 lists every method. One whose class the file declares is listed under it, and any other among the functions: a Go method on a type declared in another file of the package as `Server.Close`, which was left out, and a C++ out-of-class definition by its qualified name, `Widget::draw` (#959).
  - A C++ `.h` header was outlined as C. Its outline was labelled `c` and listed none of its classes or methods, so `--symbol` found none of them. A header is now outlined as C++ when its content uses C++ and as C otherwise, as `devops ai ast parse` reads it (#959).
- **Topology Token Counts Measure the Outline (`devops ai read --inspect --level 0`, `devops_cli.ai.inspection`)**:
  - At Level 0, `outline_tokens` and `token_reduction_pct` were a guess: six tokens a symbol plus a one-line summary. The guess left out the docstrings, bases, method lists, exports and hotspots that the outline prints. Both now count the markdown the outline renders. The guess put `inspection.py`'s own topology at 291 tokens when it renders 1351, so it claimed a reduction of 96.4% against a real 83.2% (#959).
- **The Regex Fallback Signs and Finds Declarations as Tree-Sitter Does (`devops_cli.ai.ast.fallback`)**:
  - The fallback now signs every symbol it finds with the line that declares its name, as the tree-sitter engine does. Before, a function or method held only its parameter list (TypeScript, Go, Rust, Java) or a rebuilt `(args) -> ret` (Python), and a class, struct, interface or Terraform block held no signature (#959).
  - The fallback finds Rust functions with any qualifier the language allows (`const`, `async`, `safe`, `unsafe`, `extern "C"`) and with generics, `pub fn process<T: Clone>(x: T)`. It finds TypeScript functions with generics, `function f<T>(x: T)`, and declared as `export default function` (#959).
- **Tree-Sitter Gives Go Methods Their Type and Signs a Symbol With the Line That Names It (`devops ai ast parse`, `devops ai repomap --json`, MCP `ai_ast_parse`, `devops_cli.ai.ast.engine`)**:
  - A Go method had no owner. It now belongs to the type its receiver names, through a pointer, type arguments or parentheses, as the regex fallback has it: `func (l *List[T]) Push(v T)` is `List`'s (#959).
  - A symbol under a Java annotation, a C# attribute or a TypeScript decorator was signed with the annotation's line, `@Override` or `[HttpGet("{id}")]`, with no name or return type. It is now signed with the line that holds its name, `public String toString() {` (#959).
- **`ai.timeout` and `ai.tasks.<task>.timeout` Set How Long an LLM Request Waits (`devops ai`, `devops review path|branch|pr`, `devops_cli.ai.client`, `devops_cli.ai.review.runner`)**:
  - `LLMClient` waits the timeout its caller passes, else the task's configured `timeout`, else 3,600 s. It read only the caller's, so both keys were accepted and documented but did nothing for chat, metadata, analysis, verification or compose requests (#960).
  - A review's analysis, verification and compose clients wait their task's configured `timeout`, and 1,200 s only when none is set. The review runner passed 1,200 s to all three over any configured value (#960).
  - An Ollama model resolved for pydantic-ai carries `ai.timeout` as its request timeout (#960).
  - Both keys must be positive and finite, and `docs/CONFIGURATION.md` says what `ai.timeout` sets and what applies when it is unset (#960).
- **A Provider Reply Is Read Only Up to Its Size Limit (`devops ai`, `devops review path|branch|pr`, `devops_cli.ai.client.network`)**:
  - Claude, OpenAI-compatible and Ollama chat replies, and the model lists from `/models` and `/api/tags`, are streamed through `request_limited_json`, which refuses a Content-Length over the 50 MiB limit before reading and stops reading once the decoded body passes it. The client buffered the whole body and only then checked its size, so a model endpoint, or anyone on the path to a plain-http Ollama URL, could send a multi-GB reply and exhaust the CLI's memory. With the limit lowered to 4 KiB, each of the five calls now stops a 2,000-chunk reply within its first 5 chunks; all 2,000 were read before (#960).
  - A reply that is not 2xx has its body read under the same limit, still raises the HTTP error the providers handle, and is never parsed. A reply that is JSON but not an object is refused (#960).
  - Size-limit messages name the limit in MB, KB or bytes; a 4 KiB limit read "0MB" (#960).
- **A Remote Model Goes Where Its Settings Say, or Resolving It Fails (`devops_cli.ai.pydantic_ai_bridge`, `devops_cli.ai.durable`, `devops_cli.ai.gateway`)**:
  - An `ai.api_base_url`, `ai.gateway_url` or `ai.portkey_url` that cannot be used raises a `ConfigurationError` naming that setting, and a model pydantic-ai cannot build, including one whose provider's optional package is not installed, raises one naming `ai.provider` and `ai.model` with pydantic-ai's reason, such as its "Did you mean" hint. Both returned the bare model string, so `api_base_url: localhost:8000/v1` (no scheme) sent `openai:gpt-4o` to `https://api.openai.com/v1/` with the configured endpoint and key dropped (#960).
  - Under `ai.provider: gateway` every model name is a route of the `ai.gateway_provider` gateway, sent whole as `LLMClient` sends it, so an Ollama tag such as `mistral:7b` stays a route. Under `openai`, `copilot` and `claude`, a name whose text before its first colon names no provider, such as `devops-review` or `qwen3-coder:30b`, takes the provider's prefix: `openai` and `copilot` as OpenAI chat models, the API `LLMClient` uses, with `copilot` on Copilot's API, and `claude` as `anthropic`. A provider is one this repository registers or pydantic-ai knows (`is_pydantic_ai_provider`). `litellm:` and `portkey:` models are OpenAI chat models sent to `ai.gateway_url` and `ai.portkey_url` under every provider, `ollama` included; `litellm:<model>` lost its prefix and could not be inferred, left to pydantic-ai it went to `https://api.openai.com/v1/`, and under `ollama` it was an Ollama model of that name (#960).
  - `create_pydantic_ai_agent` falls back to `PydanticAgent` only when pydantic-ai's `Agent` refuses its arguments, and `create_durable_pydantic_agent` no longer catches every error from resolving its model, so a configuration error reaches the caller. The durable factory handed the native `Agent` the bare name, which pydantic-ai sent to the vendor's endpoint (#960).
  - The fallback cascade `"cascade"` is LiteLLM's and Portkey's `devops-chat` route, then `ai.model` on Ollama itself, and `GatewayRouter.build_pydantic_cascade_model` is a route and its failover route on the router's gateway, then `ai.model` on Ollama, which a failover to `direct-ollama` names. Their bare members (`litellm`, `portkey`, `ollama` and the routes) were read as model names: building either raised pydantic-ai's "Unknown model", and under provider `ollama` every member was an Ollama model of that name (#960).
- **The Example Config's Local RAG Backends Pass the SSRF Guard (`devops review path|branch|pr`, `devops ai rag`, `devops_cli.core.validation`, `devops_cli.ai.rag`)**:
  - `validate_configured_service_url` is the one policy for service URLs from the user's own configuration: loopback (`localhost`, 127.0.0.0/8, ::1) passes without `ai.allow_private_network`, every other non-public host still needs it, and cloud metadata hosts are always refused. Qdrant, the Ollama, OpenAI and gateway embedding calls, the Ollama provider, the LLM client and `create_pydantic_ai_provider`, which builds the bridge's remote models, use it. With `config.example.yaml` as shipped, `QdrantClient("http://localhost:6333")` raised `SSRFBlockedError` and every embedding call to `http://localhost:11434` was refused, so RAG never ran; the client also refused the example's gateway at `http://localhost:4000/v1` (#960).
  - The first RAG lookup of a run that fails, such as on a vector store the guard refuses, logs one WARNING with the cause; later ones log at debug. All of them logged at debug, so a refused backend left RAG off without a word (#960).
- **`--namespace` No Longer Selects the Kubeconfig Context (`devops argo workflows`, `devops argo rollouts`)**:
  - `workflows list`, `workflows submit` (and its `--wait` poll), `workflows logs`, `rollouts list` and `rollouts status` handed `--namespace` to the Argo custom resource client as the kubeconfig context. Outside a pod, `-n argo` failed with a missing-context error, or reached another cluster when a context of that name existed. They now use the current context and send `--namespace` only as the namespace (#961).
- **A Workspace File the Command Cannot Read Is Left As It Was (`devops workspace add`, `devops workspace remove`)**:
  - A workspace file over the size limit, not UTF-8, not plain JSON, or without a `folders` list was read as empty, and `add` then saved one folder over it, dropping every folder and setting it held. VS Code accepts comments and trailing commas in a `.code-workspace` file, so a file VS Code wrote could trigger it. Both commands now print the error, say the file was left unchanged, and exit 1. A file that does not exist yet still starts empty (#961).
- **Only a Listener on 127.0.0.1:9418 Counts as a Running Git Daemon (`devops devcontainer post-start`)**:
  - Any live process named by `/tmp/git-daemon.pid` counted as the daemon. `git daemon` never removes that file, and `/tmp` is a volume that outlives container rebuilds, so after a rebuild post-start could report the daemon running and never start it. The port probe is now the only check (#961).
- **Port-Forward Records Survive Concurrent Runs and Reused Pids (`devops k8s port-forward`, `devops k8s port-forward-status`, `devops k8s port-forward-stop`)**:
  - Every read-change-save of the state file holds an exclusive lock on `port_forwards.lock` beside it, from the read to the save, and a run holds it while it starts its forwards. Two runs at once, or a stop during a start, no longer save over each other's records and leave forwards that hold their local ports but are never listed or stopped (#961).
  - `port-forward-status` with no state file returns at once and creates no `.data/k8s/` directory or lock file where it runs (#961).
  - The state file is written to a temporary file and moved into place, so a read never sees it half written (#961).
  - Each record keeps its process's start time from `/proc/<pid>/stat`. A forward counts as running, and `port-forward-stop` signals it, only while its pid still has that start time, so a pid the kernel has since handed to another process is neither listed nor sent SIGTERM. Where `/proc` cannot be read, a live pid is still enough. A state file written before this change has no start times, so it reads as no forwards and the next start saves over it; forwards it recorded keep running until ended by hand (#961).
- **A TLS Secret kubectl Rejects No Longer Deletes the Live One (`devops k8s create-tls-secret`, `devops k8s enable-tls --overwrite`, `devops tls enable-k8s`)**:
  - The commands deleted the secret and then created the new one, so a certificate and key kubectl rejects, such as a rotated certificate with the old key, or an API error left the namespace with no secret, and its ingresses fell back to the default certificate. The secret is now rendered with `kubectl create secret tls --dry-run=client -o yaml` and applied over the existing one with `kubectl apply -f -` only once it renders. Nothing is deleted. A failure shows kubectl's error and leaves the existing secret in place, and `create-tls-secret` reports `Applied TLS secret` (#961).
- **The Drift Report Says When It Could Not Be Saved (`devops ai audit-library-usage`)**:
  - A report that could not be written, to an unwritable analysis directory or a full disk, was dropped without a word, and the previous run's `api_drift_report.json` stayed in place as if current. The failure is now logged and shown as a warning (on stderr with `--json`), the previous report is removed before each write, and the command prints where it saved the report (#961).
- **`devops gh labels sync` Fails When gh Does (`devops gh labels sync`, `devops gh labels list`)**:
  - Without a token and with gh logged out, the failed `gh label list` read as no labels and every failed `gh label create` went unseen, so the command printed `Label sync complete` and exited 0. A failed `gh label` call now raises, and the command prints the error and exits 1 (#961).
  - `gh label list` is asked for up to 1000 labels. It stopped at 30, one short of `.github/labels.yml` (#961).
  - `sync_repository_labels` (`devops_cli.github.labels`) takes a typed client and calls it directly. Its fallbacks retried a call that raised `TypeError` without the repository, which no client accepts, and skipped a client lacking a method while still counting the label as created (#961).
- **Semgrep AST Scanner Timeout Realignment & Target Filtering (`devops_cli.security`)**:
  - Realigned `BaseSecurityScanner.scan` default execution timeout from `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS` (30s) to `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS` (300s), ensuring external CLI scanners executing against multi-file changesets or repository diffs do not trigger premature `TimeoutExpired` aborts (#963).
  - Filtered non-code targets (documentation markdown files, lockfiles like `uv.lock`, and binary assets) in `_build_scan_command` using `CONST_SEMGREP_EXCLUDED_EXTENSIONS`, preventing unnecessary file parsing overhead during Semgrep AST security reviews (#963).
  - Hardened `_resolve_cwd` for multi-file target lists using `os.path.commonpath` to resolve the common root directory rather than pinning the subprocess to the parent directory of the first file (#963).
- **RAG Query Latency No Longer Flattens at 5 s (`devops_cli.telemetry.instruments`, `k8s/monitoring/dashboards/devops-cli.json`)**:
  - `devops_cli_rag_query_duration_ms` buckets stopped at 5 s, below the query's own timeouts, so in any hour where more than 5% of queries took longer the "RAG Query Latency (p50, p95)" panel's p95 read exactly 5000 ms. The buckets now run to 600 s (`10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 15000, 30000, 60000, 120000, 300000, 600000` ms), past the gateway embedding request's 30 s and the default `qdrant.timeout` of 300 s, up to 600 s, the top of the range that suits a homelab Qdrant. The panel descriptions state the new cap, 600000 ms (#975).
  - The panel now reads `stage="total"`. The series earlier releases sent carry no `stage` label and buckets that stop at 5000 ms. The panel leaves them out rather than mix the two bucket sets in one quantile, so it draws only queries recorded by this release or later, from any host. The old series stay in Prometheus until retention drops them (#975).
- **Review Tables Print Untrusted Text as Written (`devops review findings`, `devops review path|branch|pr`)**:
  - `devops review findings` read finding titles, locations, personas and verdict reasons as Rich markup. A title holding a closing tag such as `[/{status_color}]` stopped the command with a `MarkupError`, and a lowercase bracket such as `[standard]` vanished. A review's dependency and network tables did the same with package names, versions, targets and statuses, so `uvicorn[standard]` printed as `uvicorn`. They are escaped now (#987).
- **Bandit Runs on Reviews of More Than 50 Python Files, and a Failed Analyzer Says Why (`devops ai review`, `devops scan report`, `devops_cli.security.bandit`, `devops_cli.security.base`)**:
  - `BanditScanner` passes `-q` in each of its command shapes: a file list, a single file and `-r <directory>`. Over more than 50 files Bandit 1.9 draws a progress bar on stdout ahead of its JSON report, so the report did not parse, and the exit code 1 that meant "issues found" was recorded as a failure. Every branch review with more than 50 changed Python files, `release/v0.2.25`'s among them, reported `! Failed during execution: Bandit` and left Bandit's findings out, as did `devops scan report` of a directory holding more than 50 Python files (#1009).
  - A scanner that exits non-zero with output that is not JSON now fails with a reason that says so and quotes the start of that output on one line, then as much of stderr as fits in 256 characters, as in `Scanner exited with code 1; output was not JSON, starting "Working... ━━━━ 100% 0:00:20 { "errors": [] …"; stderr: …`. The reason quoted only stderr, which for Bandit was its INFO log (#1009).
  - The session report's Static Analyzers table gives a failed analyzer's reason after its state, as in `failed: Scanner exited with code 1; output was not JSON, …`, with pipes escaped and line breaks folded. The console line names the analyzer and points there: `! Failed during execution: Bandit (the report's Static Analyzers table says why)` (#1009).
- **The DevSecOps Persona Reports Misconfiguration and Error-Handling Defects Again (`devops review`, `devops ai review`)**:
  - #951 defined a security finding only as a quoted path from an untrusted source to a sink, said most files have no security defect, and excused any choice the manifests or conventions document. In session `20261002-205520`, the first branch review with those prompts, 367 of 380 persona replies held no finding, and none of the four real findings earlier reviews had reported was generated: ingress from `0.0.0.0/0` in `k8s/monitoring/networkpolicy.yaml` (#953) and `k8s/otel/networkpolicy.yaml` (#913), a broad `except` in `ai/rag/investigator.py` (#423), and the `trust_remote_code` claim in `docs/VISION.md` (#921) (#1015).
  - A finding is a quoted vulnerability path or a quoted misconfiguration: the setting or line, and what it exposes or permits that its job does not need, with no untrusted source. A misconfiguration the manifests or conventions justify, by saying why it is safe, is not a finding; a comment that only restates the rule or names its sources, as the monitoring policy's does, is not a justification. The persona returns no finding only when it can quote no vulnerability, no misconfiguration, no false security claim in a document and no other defect a *Where to Look* class names, and the sentence "Most files have no security defect" is gone. On code it keeps an evidence bar: a value that reaches no sink it can quote is not a vulnerability, and most code has none. The persona's role names the setting that permits more than its job needs beside the untrusted path (#1015).
  - *Where to Look* adds **Network Exposure**, a NetworkPolicy, Ingress, Service, firewall rule or security group that admits `0.0.0.0/0`, every namespace or every pod to a port whose known consumers are fewer than that. A port the manifests or conventions say must face every source, and say why that is safe, such as an API that authenticates every request, is not exposure; a port open to every address without that reason is. Egress to every address with cloud metadata blocked is not exposure, and no NetworkPolicy rule is SSRF. A NetworkPolicy publishes no port, so the persona is asked to rate the finding MEDIUM at most unless it quotes the node port, load balancer, host port or Ingress route that does. It also adds **Error Handling**, a broad `except` that hides an unexpected error from the operator by logging it below warning or not at all, or that swallows one where failing closed matters, such as authentication, verification, a security check or data integrity, which the persona is asked to rate LOW, and higher only with a quoted consequence such as a skipped check (#1015).
  - The configuration page prompt, which NetworkPolicies, Ingresses and Services get, names **Network Exposure**: a rule that admits more sources to a port than its consumers need. Its sentence "A setting the workload does not need is not a defect", which contradicted the misconfiguration rule, now reads that a *missing* setting the workload does not need, such as a CPU limit, is not a defect (#1015).
  - The documentation prompt reports a false security claim again: a statement that the program applies a security control that the code contradicts or does not apply. #951 asked every documentation finding to quote the code line that contradicts it, which a claim about a control the code lacks cannot do. The evidence bar, the rule against advisory identifiers from memory, and the exemption for roadmaps, changelogs, task files and decision records stay as #951 left them (#1015).
  - The verifier asked every security finding for an untrusted source and a sink before it could be **Verified**, so a restored misconfiguration could not be. It now asks a vulnerability for the source and the sink, and a misconfiguration for the quoted setting and what it exposes or permits beyond its job (#1015).
  - The prompt digest changes, so reviews from before and after this change are separate arms of a prompt benchmark (#1015).
- **Passing Criteria Leave a Finding for the Verifier Instead of Verifying It (`devops review path|branch|pr`, `devops_cli.ai.review.review_environment`)**:
  - A passing verification criterion no longer settles VERIFIED. One that counts as evidence is recorded in `verified_criteria_matched`, gives the finding no confidence, and leaves it unverified, so the verifier is shown it and its verdict applies. The evidence rule tells whether a command runs the cited code and checks the outcome, not which side of the claim a pass supports. In review session `20261003-012555`, both verification criteria of a false finding on `ai/review/chunker.py:395` ("Undefined method call on PurePosixPath"; `PurePath.full_match` exists on Python 3.13 and later) asserted that `skips_persona_review` returns the right value, the opposite of the claim. Replayed under the 30 s python limit, both passed and the finding ended VERIFIED by criteria at confidence 1.0, a verdict the verifier never saw and that the report would rank first (#1043).
  - A passing invalidation criterion that counts still settles INVALIDATED, and criteria that pass on both sides still leave the finding unverified with the note `criteria-non-discriminating`. Replayed with the results they recorded, none of the 2,461 candidate findings with a passing criterion in the saved review sessions ends VERIFIED by criteria (#1043).
  - Merging duplicate findings into a VERIFIED one keeps the adjudicator of a verified input. It no longer writes `criteria` when the inputs named none, nor takes the adjudicator of an input that was not verified (#1043).
- **Running the Cited Test Counts as Evidence (`devops review path|branch|pr`, `devops_cli.ai.review.criteria_evidence`)**:
  - A `python -c` criterion that calls, as a statement of its own, the test whose definition spans the cited line, imported from the cited test module, counts as evidence: the test's own asserts are the check. A test is a module-level function named as pytest names one (`test...`) in a file pytest collects (`test_*.py`, `*_test.py`). An async test does not count, since a bare call only creates its coroutine, and neither does a call inside a `try` or handed to another function such as `pytest.raises`. A bare call of any other function still does not count: it shows only that the function did not raise for those inputs (#1043).
  - In session `20261003-012555`, the invalidation criterion of `tests/test_rag_multi_project_indexer.py:66`, a claim that the test raises TypeError, called that test and passed in 4.1 s; the finding now ends INVALIDATED by criteria instead of reaching the verifier, whose reply was cut. Filed as a verification criterion, as on `tests/test_pipeline_protocol.py:114` in session `20260928-201857`, where a claim that the test is wrong was VERIFIED by criteria, the same kind of call leaves the finding to the verifier (#1043).
- **A Hedged Title Is MEDIUM at Most, Whoever Verified It (`devops review path|branch|pr`, `devops_cli.ai.review.calibration`)**:
  - A hedged title ("Potential", "May", "Could") VERIFIED by criteria no longer keeps a severity above MEDIUM, and `CONST_REVIEW_EVIDENTIAL_ADJUDICATORS` is removed. Criteria settle no VERIFIED verdict, and the verifier's confirmation is not evidence enough to lift the cap. Replayed over session `20261001-224227`, 8 of its HIGH findings, hedged and VERIFIED by criteria, are now MEDIUM (#1043).
- **The Scanned-Clean Check Needs Advisory Wording, and the First Early Check to Fire Gives the Reason (`devops ai review`, `devops_cli.ai.review.verification`)**:
  - A finding is INVALIDATED as `deterministic:scanned_clean_dependency` only when its title or description names, as a word, a dependency this session's scan reported CLEAN with no advisory record and also uses advisory wording somewhere in that text: the word "CVE" or "CVEs", a CVE id included, a GHSA id, "advisory" or "advisories", "unpatched", "known vulnerability" or "known vulnerabilities", or "vulnerable version". The name and the wording need not be next to each other. "Vulnerable" alone and "outdated" no longer trigger it, because a CLEAN scan says only that the pinned version carries no known advisory. It says nothing about how the code uses the package, what a Kubernetes manifest does, or whether the version is current (#1044).
  - Since #948 gave the check every dependency a session scanned, any security finding that named one of them as a word was INVALIDATED with the reason `This run's own advisory scan reports <name> CLEAN`. The names included kubernetes, httpx2, keyring, pytest, docker and bandit. Among the findings were a command injection in a Kubernetes client call, an SSRF through httpx2, a path traversal in a Bandit test helper, and Semgrep's own `yaml.kubernetes.security.*` findings. Replayed with session `20261003-012555`'s 58 CLEAN dependencies over 5,904 saved candidates in 36 sessions, the check fires on 8 candidates (6 distinct, none VERIFIED or reportable in its own run) instead of 111 (83 distinct, 26 VERIFIED, 34 of them Semgrep Kubernetes findings) (#1044).
  - The early checks stop at the first one that fires. Each check writes its verdict on the finding itself, and every check used to run, so the last one to fire overwrote the reason the first gave. A manifest finding that cited `CVE-2024-xxxx` and mentioned Kubernetes best practices was given "advisory scan reports kubernetes CLEAN" instead of the placeholder-advisory reason (#1044).
- **The Slow Tier Keeps Its Embedding Model Loaded Beside qwen3-coder and Leaves Every Interactive Pool (`k8s/llm/profiles/ollama-profiles.yaml`, `k8s/llm/gateway/configmap.yaml`)**:
  - Since #1061 every Ollama tier kept one model loaded, but the gateway still sent ollama-48gib-slow both embedding groups and five chat groups, so each chat request routed there evicted the embedding model and each embedding evicted the chat model. During a review pinned to `qwen3-coder:30b`, the tier loaded a runner 10 times in four minutes, alternating bge-m3 and qwen3-coder, and 6 of 124 `/api/embed` requests waited 31 to 40 s, past the client's 30 s embedding timeout. The first such failure turns RAG off for the rest of the run (#1064).
  - ollama-48gib-slow sets `OLLAMA_MAX_LOADED_MODELS` to `2` and `OLLAMA_KEEP_ALIVE` to `-1`, so its embedding model and `qwen3-coder:30b` stay loaded together and neither reloads after 5 idle minutes. `OLLAMA_NUM_PARALLEL` stays `1` on every tier, and every other tier still keeps one model loaded (#1064).
  - The gateway sends ollama-48gib-slow no interactive or review traffic: its deployments in `devops-chat`, `devops-review`, `qwen3-coder:30b`, `gemma4:31b` and `qwen3.8:27b` are removed. At one request at a time, background work there would queue in front of review calls, and Ollama predicts a dense ~30B model too large to fit beside the embedder, so loading one evicted it. `qwen3-coder:30b` still copies `devops-review`'s qwen3-coder deployments exactly (#1064).
- **A Review's Semgrep Scan Finishes Again, Still Isolated From the Reviewed Tree (`devops review`, `devops_cli.security.semgrep`, `devops_cli.security.base`)**:
  - Since #972 a review ran Semgrep from a temporary directory and named each reviewed file by its absolute path in the tree. Semgrep 1.178.0 takes a target that is a regular file under its working directory as it is, and for any other starts a `semgrep-core` process that walks the target's whole checkout, nested worktrees and `repos/` included. Semgrep ran out of its 300 s timeout in 11 of 11 reviews and returned nothing, so they lost the findings only Semgrep makes, such as `runAsNonRoot` and `allowPrivilegeEscalation` on the Ollama DaemonSets (#1079).
  - A review now hard-links each file Semgrep scans into that temporary directory at its path in the reviewed tree, or copies it when linking fails, and names it `./<that path>`. Findings keep the reviewed tree's paths and line numbers. Only the targets are there, so no `.semgrepignore`, `.semgrep.yml` or `.semgrep/` rule of the tree reaches the scan, and a reviewed file that is a link out of the tree is left out. A file the tree names like an option, such as `--config=x.yml` or `--autofix`, or `-`, is still only a file to Semgrep. On this repository's 387-file branch review, with a local rule file and no network, the review's scan took 24 to 32 s in its four batches. One run of the same files took 8.4 to 15.5 s this way and 148.8 s with the files named from outside its working directory (#1079).
  - A review scans its files in batches of at most 100, each under its own timeout, so a batch that runs out of time loses only its own files, and the reason says which batch it was (#1079).
  - Every scanner a review or `devops scan` runs gets an empty stdin, never the caller's, such as the request stream of `devops mcp` (#1079).
- **A Scanner That Runs Out of Time Says So (`devops review`, `devops scan report`, `devops_cli.security.base`)**:
  - A timeout read `failed: Scanner execution failed: Command '['semgrep', 'scan', …` in review.md, SARIF and the CLI, cut off before the reason. It now reads `timed out after 300 s` (#1079).
- **Release Notes Fit GitHub's Body Limits (`devops release notes`, `devops release changelog`, `devops release pr`, `devops release sync-notes`)**:
  - GitHub refuses a Release body over 125,000 characters and a pull request body over 65,536, and v0.2.25's changelog section is 196,525. Notes that fit are printed unchanged. Longer notes keep every `###` category and each entry's title, drop the sub-bullets, and end with a link to the version's section of `CHANGELOG.md` at its tag; titles that still do not fit are cut at the last whole entry, with a count of those left out. v0.2.25's notes come to 22,780 characters (#1097).
  - The release PR body counts its other sections against the PR limit. Entries are read with the changelog parser the cut uses, now with markdown-it-py, and the link's anchor comes from mdit-py-plugins; both are declared dependencies, where before they arrived only through Rich and Textual (#1097).
- **Review Personas Are Shown Only the Target's Judged Claims (`devops review path`, `branch`, `pr`)**: the persona loop built its system prompt without the review's target, so a review run from another checkout was shown the working directory's disproved claims, which could suppress a valid finding. Every layer from `_execute_review_workflow` and `ReviewPipelineOrchestrator` down to `render_negative_exemplars` now requires the target, so no caller can fall back to the working directory (#1100).
- **A Review of Another Checkout Reads That Checkout's Analysis Metadata**: `--summary` and the persona loop loaded file analysis metadata from the working directory's repository; they now load it from the target's (#1100).

### Security
- **Logs Leave Loki Only by Age (`k8s/logging/loki-values.yaml`)**:
  - `limits_config.deletion_mode: disabled` keeps Loki's log delete API closed. The delete-request store that retention requires would otherwise open it, and with `auth_enabled: false` any pod allowed to reach Loki could delete logs without credentials (#550).
- **Scanner Failure Reasons Are Masked Before They Are Cut (`devops scan report`, `devops ai review`, `devops docker analyze-layers`, the `docker_analyze_layers` tool, `devops_cli.security.base`, `devops_cli.security.dive`)**:
  - A scanner's failure reason quotes an exception, stderr or the start of output that was not JSON. It reached SARIF `toolExecutionNotifications`, the CLI warnings and review.md's Static Analyzers table without masking, so a `ghp_` token or a `user:password@` URL in a scanner's error was written out as it was. `ScanOutcome` now masks every reason with `mask_secrets`, then cuts it to 256 characters (`CONST_MAX_ERROR_DETAIL_LENGTH`), ending in `…` when cut, whichever scanner or code path produced it (#915).
  - Some reasons were cut before anything masked them, which can split a credential so that no pattern matches the part left, and others were not cut at all. A scanner that raised during `devops scan report` gave a reason as long as its error: 5,124 characters for a 5,000-character error. Those early cuts are gone. Output that was not JSON is masked before its start is quoted, and every scanner reason, #1009's for output that was not JSON among them, is capped at the same 256 characters (#915).
  - Dive cut its stderr or error to 256 characters before anything masked it, so a private key it quoted lost its END marker, was not recognized, and reached `devops docker analyze-layers`, the `docker_analyze_layers` tool, and through `devops scan report` the SARIF file and the CLI. Dive's reason is now masked, then cut to the same 256 characters (#915).
- **Reviews Run Nothing From, and Take No Conventions From, the Tree Under Review (`devops review`, `devops_cli.ai.review`)**:
  - The type check that dismisses a claimed `None` dereference ran `uv run mypy --strict <file>` in whatever directory the CLI was started from. Started inside a repository under review, `uv run` synced that project and ran its build backend, and mypy loaded that project's config and plugins. The check now runs devops-cli's own interpreter in isolated mode, `python -I -m mypy --strict`, from an empty temporary directory, with devops-cli's own config, which loads only the `pydantic.mypy` plugin its `[tool.mypy]` loads. Nothing of the reviewed tree runs, even when `PYTHONPATH` names it. A target whose imports devops-cli's interpreter cannot resolve fails the check, which leaves the finding to the model verifier (#946).
  - The check keeps mypy's cache in devops-cli's cache directory (`<data dir>/cache/typecheck-probe/`), one per interpreter, and runs one probe at a time, so a cold pass over a module's imports is paid once rather than by every probe (#946).
  - `devops review branch` read `AGENTS.md` and `.devops/review.md` from the branch's working tree and gave them to the personas and the verifier, so a branch could add exemptions that suppress findings about itself. It now reads both with git where its diff starts: the merge base of the branch and its base, or `HEAD` for uncommitted changes. `devops review pr` already read them from the pull request's base and is unchanged (#946).
  - `devops review branch` no longer takes the checked-out branch as its own base when the base has no local branch. A CI checkout or single-branch clone of a feature was reviewed against `<feature>~1`, its last commit only, under conventions its earlier commits set. The base is now `origin/<base>` when only that exists, and with no base at all the diff fails (#946).
  - The conventions lookup stops at the root of a defect corpus, which its manifest marks, so a corpus under `.data/reviews/corpora/` is no longer reviewed under the conventions of the checkout around it. The manifest is read as the conventions are: at their revision, so a branch cannot add one to hide its base's conventions, and on disk only as a regular file, so a FIFO or a link to `/dev/zero` cannot hang the lookup or exhaust memory. `devops review corpus generate` copies the first source's conventions files only where the source has them, and no longer writes placeholders in their place. Each review's `profile.json` records `conventions_digest`, a digest of the conventions its prompts carried, which `prompt_digest` does not cover, and empty when they carried none (#946).
  - The conventions lookup reads only regular files within the tree under review. On disk it followed links, so a reviewed tree's `AGENTS.md` linked to a file outside it put that file's text into the prompts. A conventions file that is a link, or that resolves outside the repository, is now skipped, as the chunker skips a linked source file, and a link committed at the revision a branch review reads is skipped too, where its target's path had been read as the conventions. A project that keeps `.devops/review.md` as a link must make it a regular file. A file reached through a linked directory is skipped too, inside the tree as well as out of it, so a path review and a branch review of one tree read the same files (#946).
  - `read_file_at_revision` (`devops_cli.git.operations`) reads only a regular file: it looks the path up with `git ls-tree` and reads the blob by its object id. A directory, which `git show` printed as a listing, and a link, whose blob is the path it points to, read as absent. It accepts any path inside the repository, refusing only an empty or absolute path, one that starts with `-`, or one with a `..` part, so a branch review from a subproject whose name holds a space or a character outside ASCII reads that subproject's conventions, and a changed file named so gets its symbol delta (#946).
- **Model-Written Scripts No Longer Run in the CLI's Process (`devops_cli.ai.harness`)**:
  - `DynamicWorkflow`, `WorkflowAgent` and `CodeMode` are removed without a replacement, with their `run_workflow` and `run_code` tools and their exports from `devops_cli.ai`, `devops_cli.ai.agents` and `devops_cli.ai.harness`. Both tools ran a model-written Python script with `exec` in the CLI's own process, and neither sandbox contained it: each handed the script the `typing` and `asyncio` modules, so `typing.sys.modules['os']` reached `os`, and in `run_workflow` `asyncio.create_subprocess_exec` started processes. No command built any of the three classes (#947).
  - A gate test fails when any module in `src/devops_cli` calls the `exec` or `eval` builtin (#947).
- **The Monitoring Perimeter Admits Traefik, Not Every Pod (`k8s/monitoring/networkpolicy.yaml`)**:
  - Ingress rule 2 of `monitoring-default-perimeter` admitted `ipBlock: 0.0.0.0/0` beside its Traefik peer, on the Grafana, Prometheus, Alloy, kube-state-metrics, node-exporter, DCGM exporter and Pyroscope ports. kube-router, the cluster's policy engine, matches an ingress CIDR against pod addresses, so every pod in every namespace could query and remote-write Prometheus, which has no authentication, and read Grafana as an anonymous Viewer. The CIDR is removed and no address range replaces it. Traefik in `kube-system`, the only way in from the Cloudflare tunnel, keeps every port it had (#953).
  - `devops k8s port-forward` is unaffected: `kubectl port-forward` enters the pod's own network namespace. `devops k8s configure-urls --addressing proxy` reaches Grafana, Prometheus and Pyroscope through the API server on the control-plane node, which kube-router admits only to pods on that node, so those addresses answer only while the pods run there. `k8s/README.md` says how each path gets through (#953).
- **Qdrant Runs With the Container Security Context Its Values Declare (`k8s/llm/values-qdrant.yaml`)**:
  - The values set a top-level `securityContext`, which the `qdrant/qdrant` chart never reads, so dropping every capability never reached the pod. They now set `containerSecurityContext`, which the chart renders: user and group 1000 to match `podSecurityContext`, non-root, not privileged, no privilege escalation, a read-only root filesystem, every capability dropped, and the `RuntimeDefault` seccomp profile. The chart's own defaults had kept the root filesystem read-only, with group 2000 and no capability or seccomp settings (#953).
- **An MCP Client Cannot Name the Benchmark's Server (`benchmark_embeddings` MCP tool)**:
  - The tool refuses a `model` holding `@` or `://`, which `devops ai benchmark` reads as `model@endpoint` and sends that model's requests to, and a `provider` other than `ollama`, `claude`, `copilot`, `openai` or `gateway`. It raises `ValidationError` before any command runs. A client calling `benchmark_embeddings(provider="openai", model="x@https://<host>")` had the benchmark send `POST https://<host>/v1/embeddings` with the configured AI key as its bearer token. The model now runs on the configured servers, and naming a server stays on the command line (#954).
- **The AI Key Goes Only Where the Configuration Sends It (`devops ai benchmark`)**:
  - The embedding and chat benchmarks give a client the AI key only when the client sends it to the configured `ai.api_base_url`, `ai.gateway_url` or the configured provider's own API, compared by scheme, host and port. A `model@url` entry or a `--servers` URL anywhere else gets no key, and the embeddings engine does not take `OPENAI_API_KEY` or the keyring's key in its place. A gateway client sends to `gateway_url` whatever the model names, so it keeps the key. The `--models` help says so (#954).
- **Telemetry Stays Off When the Configuration Cannot Load (`devops_cli.telemetry.tracer`, `devops_cli.config.settings`)**:
  - A configuration layer that could not be read, or a registered `DEVOPS_CLI_*` variable that could not apply, left telemetry on and exporting to `OTEL_EXPORTER_OTLP_ENDPOINT` or `http://localhost:4318`, even when that layer set `telemetry.enabled: false`. `DEVOPS_CLI_TELEMETRY_ENABLED` and `DEVOPS_CLI_TELEMETRY_ENDPOINT` now still decide when the settings cannot load. Unless `DEVOPS_CLI_TELEMETRY_ENABLED` turns export on, it stays off, since the layer that cannot be read may be the one turning it off (#956).
- **`devops ai ast parse --query` Checks the Size Cap Before Reading (`devops ai ast parse`, MCP `ai_ast_parse`, `devops_cli.ai.ast.engine`)**:
  - A plain parse refused a file over the AST size cap of 50 MiB, but `--query` read the whole file and passed it to the parser, so an MCP client could make the server read and parse a file of any size. The query now runs through the new `TreeSitterEngine.query_file`. It applies the plain parse's size check before reading the file and the same `.h` header detection. Over the cap, it exits 1 with the same "Unsupported language or file size exceeded" error (#959).
- **A Gateway's Key Stays With the Gateway (`devops_cli.ai.pydantic_ai_bridge`)**:
  - Under `ai.provider: gateway`, a model named with a vendor's prefix, such as `openai:gpt-4o`, is a route sent to the gateway. pydantic-ai built it as a model at the vendor's public endpoint (`https://api.openai.com/v1/`) holding the configured API key, so the prompts and the gateway's key left for the vendor (#960).
- **A pydantic-ai Model Is Sent to a Private Host Only With the Opt-In (`devops_cli.ai.pydantic_ai_bridge`, `devops_cli.ai.providers`)**:
  - `create_pydantic_ai_provider` validates its base URL with `validate_configured_service_url` and takes `allow_private_network`, which the bridge passes from `ai.allow_private_network`. It allowed every host but cloud metadata, so with the opt-in off, `openai:gpt-4o` under an `ai.api_base_url` on an RFC-1918 address built a model that sent the prompts and the API key there, though `LLMClient` refuses that URL. A model whose `ai.api_base_url`, `ai.gateway_url` or `ai.portkey_url` is such a host now raises a `ConfigurationError` naming the setting; loopback still needs no opt-in (#960).
- **The LLM Client Never Sends to a Cloud Metadata Host (`devops_cli.ai.client.network`)**:
  - A base URL on a cloud metadata host is refused even with `ai.allow_private_network` set. `validate_base_url` skipped every check when private hosts were allowed (#960).
- **A Review Takes No Config or Data From the Repository It Starts In, Unless That Is devops-cli's Own (`devops review`, `devops ai review`, the MCP review tools)**:
  - Every `devops review` command reads a tree devops-cli does not own, or what a review of one wrote, and started in another repository none now reads a project config it was not told to. Started inside a repository that commits `.devops/config.yaml` naming its own `ai.gateway_url`, a review sent its model traffic, with the API key as a bearer token, to that host. A review started there reads the user-level config (`~/.config/devops-cli/config.yaml`) and, as the explicit opt-in, the file `DEVOPS_CLI_CONFIG` names; outside the review commands the project layer still applies (#972).
  - devops-cli's own repository is exempt: the one whose checkout holds the source of the devops-cli that runs, as an editable install's does, with every worktree of it. Its code already runs in the process, so a review started there reads its project config and keeps all of its data under the main worktree's `.data`, as before #972. A clone nested in that checkout, such as one under `repos/` or `.data/samples/`, is another repository, and an installed devops-cli, in site-packages or outside any repository, trusts no repository this way (`is_own_source_repository`, #972).
  - The root command holds the rule for `devops review` and `devops ai review` before it opens the command's span, which builds the process's tracer from the config. A `telemetry.endpoint` the repository's `.devops/config.yaml` named had received every span of the review, each LLM call's 200-character prompt preview among them (#972).
  - Started in another repository, a review resolves a relative data path under `~/.local/share/devops-cli` rather than under that repository, so its default data directory is `~/.local/share/devops-cli/.data`. The repository's `.data` held whatever its author committed: a learned-catalog entry recording a person's verdict on the exact claim of a real finding invalidated that SSRF finding on `urllib.request.urlopen(u)`. The hallucination catalog, the review history and baselines, the mitigations ledger, the library contracts and the LLM response and type-check caches follow. An absolute `DEVOPS_CLI_DATA_DIR`, `data.dir` or `DEVOPS_CLI_DATA_*` path is one the user named and stands, as the opt-in for keeping review data in a repository. `devops review findings`, `verify`, `stats` and the other review commands resolve the data directory as a review does, and `devops review findings` names the directory it found no session in (#972).
  - The MCP server runs `devops review` in its own process, so a command it runs while a review does also reads the user-level config and data, unless the server runs in devops-cli's own repository (#972).
- **Library Contracts Come From devops-cli's Data Directory Alone (`devops review`, `devops ai ingest`, `devops_cli.ai.review.contract_grounding`)**:
  - Contract grounding read `.data/libraries/<package>.json` relative to the working directory, and a contract the reviewed repository committed reached the persona prompt as "Verified Third-Party API Contracts (Ground Truth)", with its docstring telling the model not to report SQL injection. Contracts are read from `libraries/` under the data directory (`library_contracts_dir`), and contracts there that lie inside the tree under review are refused with a warning, even in a data directory the user named there, unless that tree is devops-cli's own repository (#972).
  - `devops ai ingest library` writes, and `devops ai ingest index-libraries` and `query-library` read, that directory by default, where review data is kept, as a review does, and so do the drift auditor and the MCP `resource://libraries/indexed` resource; `--dir` and `--contracts-dir` still name another (#972).
- **A Review's Scanners Read No Config From the Reviewed Tree (`devops review`, `devops_cli.security`)**:
  - Bandit, kube-linter, Pluto, Trivy, Gitleaks and Semgrep ran in the reviewed file's directory with no config of devops-cli's own. A committed `.kube-linter.yaml` with `checks: {doNotAutoAddDefaults: true}` took a privileged `nginx:latest` Deployment from 7 findings to 0, and a `.trivyignore` hid Trivy's Dockerfile findings. A review now runs each from a temporary directory outside the tree, and hands kube-linter (`--config`), Trivy (`--config`, `--ignorefile`), Gitleaks (`--config`, `--gitleaks-ignore-path`) and Bandit (`--ini`) devops-cli's own files: each scanner's defaults, and ignore files that ignore nothing. Pluto reads no such file, and Semgrep takes its rules from `--config` alone and applies no `.semgrepignore` to the files a review names. A project's own scanner config does not count. `devops scan` and the other scanner commands still read the project's (#972).
- **The None-Dereference Probe Claims Nothing the Reviewed Module Arranged (`devops review`, `devops_cli.ai.review.verification`)**:
  - The probe took a strict mypy pass as proof that a claimed `None` dereference cannot happen, but the reviewed module controls that pass. It now claims nothing of a module holding a `type: ignore` comment or an inline `# mypy:` line, or whose cited lines hold an expression of type `Any`, which a second, warm mypy pass names: it checks a copy of the module with `# mypy: disallow-any-expr` appended (`--shadow-file`), isolated as the probe is. A first-line `# mypy: ignore-errors` or `# type: ignore`, a `# type: ignore[union-attr]` on the line, and an `-> Any` return had each let it INVALIDATE a real `len(find(name).upper())` dereference of an `Optional[str]` (#972).
  - Each suppression is read where mypy reads it, before mypy runs: `type: ignore` from the module's comments, and `# mypy:` from every line that starts with it, a line inside a string too, as mypy 2.3.1 takes it. The module is read as mypy decodes it, after any byte order mark, and a module that declares an encoding other than UTF-8 gets no claim. A `# mypy: ignore-errors` line inside a triple-quoted string, and a `# mypy:` line spelled `+ACM- mypy:` under a `# coding: utf-7` declaration, had each let it INVALIDATE the same dereference (#972).
- **The MCP Profile Tool Runs Nothing, and `devops telemetry profile` Runs Only devops-cli (`telemetry_profile`, `devops telemetry profile`)**:
  - The `telemetry_profile` MCP tool took a `command`, which `devops telemetry profile` split with `shlex` and ran with the user's full environment, so a prompt-injected agent with the server attached could run any program with every credential in reach. The tool now takes only a required `trace_id` and shows the waterfall Jaeger recorded for that trace. A call that still passes `command` is refused as a parameter the tool does not have, and nothing runs (#980).
  - `devops telemetry profile <command>` runs only a devops-cli command line: its first word must be `devops`, and the rest runs as `python -P -m devops_cli.entry`, the entry point the `devops` script calls, under the running interpreter, so another `devops` found first on PATH is not what runs either. `-P` keeps the working directory off the child's import path, as it is for the `devops` script, so a `token.py` or a `devops_cli/` in the directory profiled from does not run in place of devops-cli's own code. Any other command line, or one `shlex` cannot split, is refused with a message and exit 1 before a process starts. The child keeps the full environment, as it would run directly, since only devops-cli itself, imported from where it is installed, receives it (#980).
  - `docker_sandbox` ends its options with `--` before the workload command, and the lazy proxy in front of each command group passes `--` on to the command behind it, where it had consumed it. A workload command starting with an option, such as `["--root", "id"]`, set `devops docker sandbox`'s own `--root` and ran the container as root, and `sandbox_exec(command=["--workdir", "/", "id"])` set its workdir, although `sandbox_exec` and `sandbox_deploy` already sent `--`. A user's `devops sandbox exec <id> -- <command>` reaches the sandbox intact the same way (#980).
- **Loki Admits Only the OpenTelemetry Collector from `otel` (`k8s/logging/networkpolicy.yaml`)**: Loki's 3100 ingress from `otel` named the whole namespace, and Loki runs without authentication, so Jaeger or any later `otel` workload could push and query logs. The peer now combines the namespace with the collector release's pod labels; the shape was checked live under the cluster's kube-router, which enforces it with `ports` on ingress (#1100).
- **The Loki Peer Is Tied to the Collector Release It Names**: a test checks the policy's `app.kubernetes.io/instance` and `app.kubernetes.io/name` against the `otel-collector` release `devops k8s` installs and its chart, so renaming the release or overriding the chart name fails the tests instead of cutting the collector off from Loki (#1100).

## [0.2.24] - 2026-10-01

### Added
- **Stack Dashboards Chart Only What Their Exporters Serve (`k8s/monitoring/dashboards/`)**:
  - The LLM gateway, OpenTelemetry collector and new Prometheus server dashboards query only series their exporters serve, checked in tests against captured exporter output, with no `or vector(0)` fallback, so a panel without data reads "No data" instead of zero. vLLM and the unverified Qdrant row are gone, and the collector's own telemetry is scraped through pod annotations (#693).
- **devops-cli Dashboards Chart What the CLI Sends (`k8s/monitoring/dashboards/`, `devops grafana dashboards sync`)**:
  - The devops-cli and AI spend dashboards chart command latency at p50, p95 and p99, error share by command, findings by severity, and reviews by target type, reading every counter through `rate()` or `increase()`. Panels say when a value is approximate, and grouped panels no longer draw an unlabelled zero series (#692).
  - A kustomize `configMapGenerator` provisions six dashboards through the Grafana sidecar in place of the hand-copied ConfigMaps, and `dashboards sync` skips dashboards Grafana reports as provisioned (#692).
- **SARIF Runs Reflect What Each Scanner Did (`devops scan report --sarif`)**:
  - Only a scanner that ran gets a SARIF run, zero results included, with `invocations[].executionSuccessful` and its start and end times. A scanner that was unavailable, failed, not applicable or fell back to built-in patterns gets no run, only a notification on devops-cli's own invocation, so an upload never closes a tool's alerts for a scan that did not happen, and built-in pattern findings are attributed to devops-cli rather than to the real tool (#708).
  - Non-gating findings, such as Dive's efficiency score, are emitted at `note` level as `problem.severity: recommendation`, without a `security-severity` (#708).
  - Emitted documents are validated against the vendored OASIS SARIF 2.1.0 schema in tests (#708).
- **Roadmap Planning Glossary & GitHub-Source ADR (`CONTEXT.md`, `docs/adr/`)**:
  - Added `CONTEXT.md`, the glossary for release planning and the roadmap jobs, and `docs/adr/0001-github-is-the-roadmap-source.md`, which makes GitHub issues, milestones and the project board the roadmap's source of truth (#746).
  - Scheduled the roadmap jobs in `docs/ROADMAP.md` (#739-#744, with #745 in the backlog), revised the #697 and #704 entries, and removed the superseded #418, #696 and #699 entries (#746).
- **Roadmap Service Decisions, Machine-Account & Polling ADRs (`CONTEXT.md`, `docs/adr/`)**:
  - Resolved the glossary's open boundaries (Item, Candidate, Blocked, Dependency, Stalled, Cut, Current release, Critical fix, Value, Effort, Reprioritization, Closure) and added Service, the homelab deployment that runs the roadmap jobs (#756).
  - Added `docs/adr/0002-roadmap-jobs-act-as-a-machine-account.md` and `docs/adr/0003-polling-is-how-the-roadmap-sees-changes.md`, revised the #739-#743 roadmap entries, moved #741 to v0.2.26 beside #752 and #753, and added #754 and #755 to the backlog (#756).
- **Architecture Review Planning (`CONTEXT.md`, `docs/ROADMAP.md`)**:
  - Added the Code review glossary terms (Finding, Verdict, Review session, Known false positive) (#782).
  - Planned the architecture review's ten deepening candidates and five defects as #767-#781: the gitleaks list-target regression as a v0.2.24 critical fix, the roadmap store in v0.2.25, the GitHub session in v0.2.26 and the rest in the backlog (#782).
- **Dashboard Keeps Its Place Across Refreshes (`devops dashboard`, `devops tui`)**:
  - A refresh keeps each table's highlighted row and its horizontal and vertical scroll, on every tab, instead of returning to the first row every five seconds. Rows carry stable keys, so repeated records stay separate rows and a record that vanishes leaves the cursor at its index (#684).
  - The AI Review findings sub-tab shows the highlighted finding's full record in a detail pane beside the table, toggled with `i`, with model-written markup and control characters shown literally. Every finding of a session is listed, not just the first 50 (#684).
- **Truthful Pod Status, Filters and a Pod Inspector (`devops dashboard`, `devops k8s pods`)**:
  - STATUS and READY match `kubectl get pods` wherever pods are listed: the dashboard, `devops dashboard --summary`, `devops k8s pods` and `--watch`. The Kubernetes tab's banner names the context, the Ready nodes and the unhealthy pods, or the context and the real error when it cannot connect (#686).
  - Namespace and text filters survive refreshes and keep the highlighted pod on screen. Logs follow a pod's default container, `c` cycles containers, a replaced log stream is closed, and `e` opens the pod's containers and recent events. The Minikube probe is gone (#686).
- **Monitoring Stack on Grafana k8s-monitoring (`k8s/monitoring`, `devops k8s deploy-stack`)**:
  - kube-prometheus-stack is replaced by Grafana's `k8s-monitoring` chart with Alloy collectors for metrics, pod logs and events, and Prometheus keeps metrics for 30 days (#734). Loki does not yet delete logs by age, because its compactor retention is off; #550 turns it on.
  - The Prometheus server and Grafana run as their own charts again, cluster CPU metrics are restored, duplicate scrape jobs are off, and the Kubernetes views dashboards default to the homelab cluster (#738).
  - Traefik serves ingress routes for the monitoring services, and the monitoring perimeter admits it (#734).
  - The OpenTelemetry collector remote-writes devops-cli metrics to Alloy's Prometheus receiver at `/api/v1/metrics/write`, the only path it serves (#829).
  - `devops k8s deploy-stack` applies the `prometheus` Service that Alloy writes to and Grafana queries, and the Services `devops k8s port-forward` targets. No chart creates them (#912).
- **Multi-Node Ollama Profiles (`k8s/llm/profiles`)**:
  - Ollama runs as per-VRAM-tier DaemonSets behind `ollama-<n>gib` Services, and the LLM gateway routes every model group to them (#734).

### Changed
- **MCP Tool `k8s_chaos` Previews by Default**:
  - `experiment` is the positional argument, and a new `dry_run` parameter (default `true`) passes `--dry-run`, so the tool runs an experiment only when `dry_run` is false (#836).

### Removed
- **LightLLM Inference Backend (`devops_cli.ai`, `k8s/llm`)**:
  - Fully removed the unused `ghcr.io/modeltc/lightllm` inference backend, including `k8s/llm/lightllm/` manifests, `CONST_AI_BACKEND_LIGHTLLM`, `GatewayRouter.scale_lightllm()`, the `devops-cli-ai_lightllm_scale` MCP tool, and all associated CLI, configuration, and test references.
- **MCP Tools and Parameters With No Command Behind Them**:
  - The `ai_architecture` tool, which called a nonexistent `devops analyze architecture`, and the parameters `repos_sync(all_repos)`, `k8s_audit(namespace)` and `k8s_chaos(action)`, which their commands never took (#836).
- **Squid Forward Proxy (`k8s/squid`)**:
  - The Squid egress proxy, its CA bundle and its exporter are removed (#734). An existing cluster keeps the namespace until it is deleted: `kubectl delete namespace squid`.
- **vLLM Deployment Profiles (`k8s/llm/profiles`, LLM gateway)**:
  - The vLLM DaemonSets, their `vllm-<n>gib` Services and the gateway's vLLM routes are removed in favour of the Ollama profiles (#734). An existing cluster keeps the model caches until they are deleted: `kubectl -n llm delete pvc vllm-model-cache vllm-single-model-cache`. The remaining vLLM references in code are #820.
- **kube-prometheus-stack (`k8s/monitoring`)**:
  - The kube-prometheus-stack release is replaced by k8s-monitoring (#734) and the separate Prometheus and Grafana charts (#738). Its Prometheus Operator CRDs stay installed: the `prometheus-operator-crds` release now owns them (#819), so do not delete them by hand. The alias Services that kept its names working are #818.

### Fixed
- **Branch Analysis Reads the Base Revision Again (`devops analyze branch`, `devops review`)**:
  - `symbols_removed` lists the symbols a branch removed again, so a review's "cites a removed symbol" check works. Since f93231b (#738) the base file was read as a pathspec and came back empty. Enhanced branch analyses cached since then must be regenerated with `devops analyze branch --update-all` (#787).
- **Kubernetes Monitoring Stack Integration & Dashboard Metrics (`k8s/monitoring`)**:
  - Configured `kube-state-metrics` with `metricLabelsAllowlist` and extra collector `endpoints` to emit resource labels and endpoint info for Kubernetes Views dashboards (#825).
  - Expanded Alloy cAdvisor and KSM `metricsTuning.includeMetrics` to capture container CFS throttling, OOM events, network errors, and pod container status metrics (#825).
  - Permitted port 9153 (TCP) in monitoring NetworkPolicy egress, so the Prometheus server's `kubernetes-service-endpoints` job can scrape CoreDNS through the `kube-dns` Service's scrape annotations (#825).
- **Gitleaks Scans Every File of a List Target (`devops_cli.security.gitleaks`)**:
  - A list target, such as the files of a review, now runs Gitleaks once per file and merges the outcomes, keeping every finding and the worst status. Before, the binary scanned only the first file, and since #763 the built-in patterns did too (#781).
- **Board-Owned Project Status and Truthful Reconciliation (`devops gh project reconcile`, `devops gh project sync`)**:
  - The board owns Status: reconcile sets it only when unset, or when an item's state forces Done, In Review or In Progress, so manual triage is no longer reverted. Status labels match exactly, Priority only fills an unset field from its label, and Category, Value and Effort are no longer inferred (#703).
  - `devops gh project reconcile` lists every field change with its old and new value and the source that decided it, and refuses to guess a board number when no board matches the template (#703).
  - Failed reads of the board, issues or pull requests now raise instead of reading as empty, roadmap sync and release epics read every issue rather than the first 200 or 300, and each pull request is reconciled once (#703).
- **Quality Gate Within Its Five-Minute Budget (`devops ci`, `tests/`)**:
  - The secops dry-run tests enable dry-run mode instead of running trivy, kube-linter and pluto over the whole workspace until they time out (#748).
  - The test network guard now fails external DNS lookups too; tests that validate egress against a resolving hostname declare the `public_dns` fixture (#748).
  - `devops ci` warns when the workspace is on a 9p or drvfs share of a host folder, and lists pytest's slowest tests when the test step runs past the 5-minute budget (#748).
- **Structured Replies Keep Their Answer Beside Bracketed Prose (`devops_cli.ai.response_repair`)**:
  - A reply whose prose holds brackets, such as a markdown link or `items[0]`, keeps its fenced answer, so review personas keep their findings and agent replies validate against their schema (#786).
  - A lone fenced block is read exactly from its opening fence, so a fence inside one of its strings cannot cut it short and a fenced `write_file` call keeps its content's final newline (#786).
- **Harness, Constellation and Telemetry Profile Report Only What Ran (`devops ai harness`, `devops ai constellation`, `devops telemetry profile`)**:
  - `ai harness status` shows the configured provider and model with every slot `configured`, instead of a hard-coded `claude-3-7-sonnet` with every slot `attached`. `ai harness run` and `offload` report the local search they ran and what it found, without templated model "Tier 1/Tier 3" text, token estimates, or the unused `--frontier-model`/`--local-model` options (#710).
  - `ai quiesce`, `ai failover`, `ai resume` and `ai constellation` set, record and show a flag, and say so. Task registration, which nothing called, and the per-task counts, `--drain-timeout` and failover's `--force` are removed; `ai gateway failover` reroutes requests (#710).
  - `telemetry profile <command>` reads the command's trace back from Jaeger, waiting until it stops growing, and exits non-zero without a command or trace, with telemetry export off, or when no spans reach Jaeger. The `sample.*` fallback spans and the unused `--last` are removed, and the MCP tool passes the command positionally (#710).
- **The Workspace Tripwire Passes From a Linked Worktree (`tests/conftest.py`)**:
  - `uv run devops ci` no longer fails from a linked worktree. The #749 tripwire required `.git/index`, which a linked worktree lacks, so it reported every file the gate regenerates as modified by tests; git now finds the index itself (#824).
- **Deploy-Stack Installs the Prometheus Operator CRDs (`devops k8s deploy-stack`, `devops k8s teardown-stack`)**:
  - The infra stack installs `prometheus-community/prometheus-operator-crds` before k8s-monitoring and dcgm-exporter, whose ServiceMonitors need its CRDs. Since #734 removed kube-prometheus-stack, a cluster without leftover CRDs got no Alloy, and so no cluster metrics, pod logs, or gateway and GPU metrics. Teardown leaves the CRDs in place, and they carry `helm.sh/resource-policy: keep` (#819).
  - Adoption of pre-existing resources handles cluster-scoped ones such as leftover CRDs, annotates the release's namespace that Helm checks, and retries until every leftover is adopted or a retry fails unchanged (#819).
- **The Finding Detail Pane Opens Each Finding at the Top at Once (`devops dashboard`)**:
  - Highlighting another finding scrolls the detail pane to the top immediately instead of after the next screen refresh, which a slower machine had not always drawn; CI failed intermittently on it (#834).
- **Tests Never Reach Port-Forwarded Services (`tests/conftest.py`)**:
  - The test network guard refuses loopback connects to any port the test process is not listening on, and a port refuses again once its listener closes, so a workstation's port-forwards (OTLP collector, Valkey, Ollama, ArgoCD) are never reached by the suite; one run had made 5,716 such connects. The refusal is the `ConnectionRefusedError` clients already handle (#837).
  - `EmbeddingsEngine` no longer skips its Valkey probe under pytest, and `test_popeye_dry_run` no longer runs the real popeye binary (#837).
- **MCP Tools Call Commands That Exist (`devops mcp`, `devops docs check`)**:
  - Twelve MCP entry points called commands or options the CLI does not have and failed on every call. They now call real commands: `benchmark_embeddings` and `benchmark_suite` run `devops ai benchmark`; `scan_gitleaks`, `scan_semgrep` and `scan_checkov` run `devops scan secrets`, `sast` and `iac`; `resource://workspace/status` runs `devops repos list`; `scan_complexity` passes `--max-indent`; `resource://argo/fleet/status` no longer passes `--json` (#836).
  - `devops docs check` resolves every `uv run devops` argv in the MCP server against the real command tree without running it, and reports each defect at its server line (#836).
- **MCP Tools Refuse Coerced Arguments Before They Run (`devops_cli.ai.mcp`)**:
  - Tool arguments are validated against each tool's published schema before its handler runs, for listed and withheld tools alike. A boolean, string or integral float is refused where an integer is expected: `review_pr` with `{"number": true, "post": true}` had built `devops review pr 1 --post`. A refusal names each parameter once, with the expected type and the allowed parameters, and never echoes a value. Rejected inputs no longer reach FastMCP's warning log, and `jsonschema` is a runtime dependency (#862).
- **Review Self-Improvement & Verification Feedback Loop (`devops_cli.ai.review`, `devops_cli.security`)**:
  - Remediated session `20260928-160843` findings, eliminating native secret scanner false positives, tautological criteria auto-promotions, and cluster overlay networking hallucinations (#682).
  - Anchored native fallback secret patterns with `\b` word boundaries and tightened OpenAI key pattern to `\bsk-(?:proj-)?[A-Za-z0-9]{32,128}\b`, preventing `task-*.md` markdown links from falsely triggering secret detection (#682).
  - Implemented `CONST_SECRET_PLACEHOLDER_MARKERS` and `_is_placeholder_secret` to filter out documentation and illustrative placeholder tokens (#682).
  - Implemented `_is_tautological_verification_command` in `review_environment.py` to prevent text-search (`git grep`, `grep`) and reflection commands (`__code__.co_varnames`, `hasattr`, `getattr`) from falsely promoting findings to verified status (#682).
  - Broadened `HALLUCINATION-K8S-CLUSTER-OVERLAY-HTTP` in `common_hallucinations.json` and verification prompts to cover internal container-to-container and backend service HTTP communication (#682).
  - Added `HALLUCINATION-OFFLINE-PRICING-URLSPLIT` and `HALLUCINATION-MITIGATION-LEDGER-INITIAL-EMPTY` to prevent false SSRF and absent-mitigation claims on offline pricing calculators and dynamic audit ledgers (#682).
  - Added `_sanitize_api_key_header` in `gateway.py` to strip newlines and reject non-ASCII/CRLF injection characters (#682).
  - Hardened URL scheme validation in `gateway_bench.py` before `urllib.request.urlopen` (#682).
  - Enforced strict regex format `^[a-zA-Z0-9_\-\.]+$` on `run_id` in `run_store.py` rejecting `..` traversal (#682).
  - Narrowed exception handlers in `install_tools.py` and guarded git directory pointer resolution in `tracer.py` against `(OSError, RuntimeError, ValueError)` (#682).
  - Validated revisions and paths before the git invocations in `analyze.py` (#682).
  - Added `_validate_mcp_arg("session_id", ...)` in MCP `review_findings` (#682).
  - Updated `src/devops_cli/ai/tasks/verify_finding_system.md`, `src/devops_cli/ai/tasks/review.md`, and `src/devops_cli/ai/personas/devsecops/prompt.md` with explicit falsification rules against tautological criteria, documentation placeholders, and internal cluster networking (#682).
  - Added Calibration Record for session `20260928-160843` to `docs/SELF_IMPROVEMENT.md` (#682).
  - Exported refreshed feedback dataset with 1,219 findings via `devops review export-feedback` (#682).

### Security
- **`web_fetch` Vets Every Redirect Hop Before Sending It (`devops_cli.ai.common_tools`, `devops_cli.http.broker`)**:
  - A redirect chain could reach a link-local or private address: only the first URL and the final response were checked. Now each hop goes through the HTTP broker's request hook before it is sent. Only http and https are allowed, the domain lists apply with case and trailing dots ignored, and the address must be public whatever `DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK` says. Both broker clients follow at most 10 redirects (#860).
  - Each fetch uses its own client, so no cookies carry over between fetches, and a request's egress policy can only add restrictions to the broker's own SSRF check (#860).

## [0.2.23] - 2026-09-28

### Added
- **GPU-Architecture Inference Placement & Gateway Routing (`devops_cli.k8s`, `devops_cli.ai`)**:
  - Scheduled inference engines dynamically by GPU compute architecture (`nvidia.com/gpu.family` and `nvidia.com/gpu.architecture`), mapping dual-GPU Ampere+ nodes to vLLM Qwen2.5-Coder-32B at tensor parallel 2 with 64K YaRN context, single-GPU Ampere nodes to vLLM Qwen2.5-Coder-14B, and legacy hardware to Ollama (#453, #654, #655, #668).
  - Adopted throughput-weighted `simple-shuffle` gateway routing across the `devops-review` model group without artificial concurrency caps, achieving ~2 req/s throughput scaling (#467, #468, #668).
  - Ephemeral debug container script pipelining via stdin to prevent Linux `MAX_ARG_STRLEN` (128KB) overflow on large prompts during gateway tuning, with concurrency recommendations and label-keyed weight matching (#470, #669, #677).
  - Consolidated the LiteLLM Gateway as the single authenticated cluster entry point with automatic route discovery and credentials enforcement (#455, #469, #471).
  - Forwarded Ollama ranged blob pulls through the Squid forward proxy unchanged, enabling large model downloads from Cloudflare R2 (#460, #461).
  - Deployed Ollama as a headless StatefulSet with per-pod DNS routing and one gateway deployment per GPU node (#463).
- **Multi-Persona Code Review Engine & Quality Hardening (`devops_cli.ai.review`)**:
  - Added construct-aware finding location validation using Python AST to relocate drifted findings to precise line spans and support removed-symbol finding exemptions (#403, #436, #593, #659).
  - Enforced finding schema verdict polarity validation (`observed_value` vs `expected_value`) and deterministic pre-verification invalidation of contradictory polarity hallucinations (#435, #635).
  - Bound verification verdicts by finding identity and normalized location rather than list position, preventing verdict misattribution (#403, #436, #660).
  - Structured error reflection for Pydantic schema validation retries, preserving field-level validation errors and actionable fix hints (#437, #656).
  - Synthetic defect corpora generation and scoring (`devops review corpus generate` / `score`) across 9 injection templates for measured defect recall tracking (#473, #476).
  - Per-stage execution profiling and telemetry recording wall time, LLM calls, prompt/completion tokens, and serving backends in `profile.json` and spend ledger (#473, #474, #661, #664).
  - Per-call token caps on review and verification replies (`limit_completion_tokens`), preventing runaway generation delays (#494, #496).
  - Project conventions resolution nearest-first from base ref or reviewer checkout to prevent PR branches suppressing findings (#524, #658).
- **Cloudflare Tunnel GitOps & Cluster Ingress Automation (`devops_cli.k8s.cloudflared`, `devops_cli.k8s.ingress`)**:
  - Added declarative `cloudflared` multi-replica deployment with non-root security context (`runAsUser: 65532`, `readOnlyRootFilesystem: true`), token secret mapping, and dedicated network policy isolation (#646, #651).
  - Deployed Traefik Ingress Controller as an internal `ClusterIP` service with wildcard `*.homelab.<domain>` routing, client host-header preservation, and pre-configured ingress routes for `open-webui`, `llm-gateway`, `kube-prometheus-grafana`, and `argocd-server` (#646, #651).
  - Hardened Cloudflare DNS client pagination, unmanaged record protection, tunnel ingress preservation, and public IP bypass policy options (#666, #676).
- **Host Sandbox & Process Group Isolation (`devops_cli.sandbox`, `devops_cli.core.process`)**:
  - Implemented guarded POSIX process group isolation (`start_new_session=True` on `Popen`) with safe hierarchical group termination guarding PID 1 and caller process group (#440, #663).
  - Added ephemeral container streaming output byte caps, bounded ring buffers (`collections.deque(maxlen=1000)`), and read-only git worktree volume mounts (#449, #663).
  - Isolated agent workspace data tier (`.data/agent/`) preventing temporary review artifacts from polluting user workspace data (#553, #616).
- **Roadmap & Milestone Scope Governance (`devops_cli.github`)**:
  - Added the Autonomous Milestone Scope Governor & Release Air-Lock Oracle deliverable and mathematical scope convergence tracking to prevent milestone horizon inflation cascades (#678).
  - Reconciled task file traceability and backlog synchronization requiring completed deliverables and issue links (#489, #492, #679).
  - Automated release-branch issue closure (`devops gh issues close-merged`) closing pull-request referenced issues across release branches (#342, #366).

### Fixed & Hardened
- **Security Sanitization (`devops_cli.security.sanitizer`)**: Bracket-balanced credential detection and attribute chain validation in code sanitizers (#662, #676).
- **Credential Masking (`devops_cli.security.sanitizer`)**: Capitalized word discrimination preventing ordinary prose being treated as credentials (#397).
- **Keyring Credentials (`devops_cli.security`)**: Keyring credential resolution hardening and host-credential gap elimination (#485).
- **Pull Request Readiness (`devops_cli.commands.pr`)**: Blocked PR readiness checks on drafts, uncompleted task specs, and failing CI checks (#398, #400).
- **DevContainer Prefix Resolution (`devops_cli.commands.devcontainer`)**: Handled URL strings gracefully when resolving SSH key prefixes from JSONC manifests (#488).
- **Background Pipes (`devops_cli.core.process`)**: Drained background shell pipes into bounded ring buffers, avoiding deadlock on large process outputs (#449).
- **Port-Forward Process Groups (`devops_cli.k8s.port_forward`)**: Isolated port-forward daemons into dedicated process groups with graceful teardown (#440).
- **Self-Agreement Confidence Stripping (`devops_cli.ai.review`)**: Removed ungrounded self-agreement confidence heuristics in favor of external tool verifications (#402).

## [0.2.22] - 2026-09-22

### Added
- **Cluster-Native Service Addressing (`devops_cli.k8s.service_proxy`, `devops_cli.k8s.service_http`)**:
  - Introduced the `k8s://namespace/service:port` scheme, resolving endpoints through the Kubernetes API server's Service proxy so the same configuration works on any cluster without a local port-forward (#369).
  - Routed dashboard, Grafana, Prometheus, Jaeger, ArgoCD and Open WebUI endpoints through cluster-native addressing, and added `devops k8s configure-urls --addressing proxy` to record them (#370).
  - Reached the Qdrant vector store through the cluster API rather than `localhost:6333`, making `devops ai rag query` work with no port-forward running (#379).
- **Native In-Process Kubernetes Engine (`devops_cli.k8s.informer`, `devops_cli.k8s.service`)**:
  - Replaced `kubectl` subprocess invocations with a dynamic informer and an in-process service client, with bounded FIFO caches and per-entry TTLs (#307, #336).
- **Docker Engine API Client (`devops_cli.docker`)**:
  - Routed every container, image, network, volume and registry operation through the Engine API socket instead of the `docker` binary (#308, #348).
- **Native Argo Custom Resource Manipulation (`devops_cli.argo`)**:
  - Manipulated Argo Workflows and ArgoCD custom resources directly via the Kubernetes API, with localized name validation (#309, #351).
- **In-Process Terraform & OpenTofu Analysis (`devops_cli.tf.analysis`)**:
  - Parsed HCL and state in-process to build dependency graphs and detect drift without invoking the Terraform binary (#310, #352).
- **Valkey Connection Pooling & Unified Cache Tiers (`devops_cli.valkey`)**:
  - Pooled connections with idle expiry, batched commands, and consolidated the separate caching tiers behind one client (#312, #356).
- **Hybrid Retrieval & Vector Quantization (`devops_cli.ai.rag`)**:
  - Fused BM25 lexical ranking with dense embeddings and quantized stored vectors, reducing index size while preserving recall (#313, #357).
- **Client-Side Prometheus Analysis (`devops_cli.prometheus`)**:
  - Validated PromQL locally before dispatch and analysed returned series client-side, removing round trips for malformed queries (#314, #358).
- **Declarative Grafana Dashboards (`devops_cli.grafana`)**:
  - Built dashboards from declarative definitions and linted them statically, catching malformed panels before upload (#315, #359).
- **Reactive TUI Dashboard (`devops_cli.ui`)**:
  - Refreshed each dashboard domain on its own worker thread and virtualized log tailing behind a bounded buffer, so a fast producer cannot outrun the terminal (#317, #361).
- **Unified SARIF Security Engine (`devops_cli.security`)**:
  - Consolidated every scanner behind a single SARIF 2.1.0 pipeline with shared normalization and suppression (#321, #363).
- **Secret Resolution & Vault Lease Lifecycle (`devops_cli.security`)**:
  - Unified credential resolution across keyring, environment and Vault, and managed lease renewal and revocation explicitly (#311, #353).
- **Structured AI Workflows, Prompt Caching & Token Governance (`devops_cli.ai`)**:
  - Implemented Pydantic AI structured workflows, a prompt cache, and a token-bucket governor that carries overdraft as debt so the long-run rate holds (#320, #341).
- **FastMCP In-Process Execution (`devops_cli.ai.mcp`)**:
  - Executed MCP tools in-process with dispatching and resource subscriptions rather than spawning a server (#318, #338).
- **GitHub GraphQL Consolidation & ETag Caching (`devops_cli.github`)**:
  - Batched GraphQL queries, cached responses by ETag, and paced requests against live quota rather than a fixed window (#316, #337).
- **Release-Branch Issue Closure & Project Automation Inspection (`devops_cli.github.issue_closure`)**:
  - Added `devops gh issues close-merged`, closing the issues a pull request declared when it merges into a release branch -- GitHub honours closing keywords only on the default branch, so those references were previously inert (#342, #366).
  - Added `devops gh project workflows list`, reporting which built-in project automations are enabled and what each should be configured to do (#343, #381).
- **Output Format Join Point & Terminal Capability Negotiation (`devops_cli.output`)**:
  - Added `emit_serialized`, rendering any payload as JSON or YAML from one place, and made YAML output portable rather than Python-tagged (#391).
  - Restored Rich's colour negotiation, so `NO_COLOR`, a non-TTY destination and `TERM=dumb` take effect (#391).
- **DevContainer Tooling (`devops_cli.commands.devcontainer`)**:
  - Added the Claude CLI and VS Code extension to the devcontainer configuration and lifecycle (#346, #347).

### Fixed & Hardened
- **Trace Context Propagation (`devops_cli.telemetry`)**: Injected W3C `traceparent` into child process environments; the return value of the injector had been discarded at both call sites, so no child ever received a parent span (#319, #362).
- **SSH Host Key Verification (`devops_cli.crypto.known_hosts`)**: Verified host keys against `known_hosts` before trusting them, including hashed entries, `@revoked` markers and `[host]:port` forms (#322, #364).
- **CI Cache Correctness (`devops_cli.ci.cache`)**: Made the workspace fingerprint content-addressed, so staging or committing a file no longer invalidates a verified tree and the pre-push gate can reuse the run that preceded it -- 3m51s to 8.7s (#375). A passing run is now recorded even when `--no-cache` skipped reading one (#389).
- **Secret Masking (`devops_cli.security.sanitizer`)**: Masked credentials rather than sentences mentioning them; the keyword rule had rewritten "unify secret resolution" to "unify `<masked-token>`", and that corruption reached published release descriptions (#392).
- **Kubernetes Context Handling (`devops_cli.k8s.context`)**: Honoured the configured cluster context when connecting, and stopped the devcontainer post-start script overwriting it.
- **Dry-Run Semantics (`devops_cli.main`)**: Honoured an exported `DEVOPS_CLI_DRY_RUN` instead of discarding it, without letting a `--dry-run` flag latch for the life of the process (#388).
- **Terminal UI (`devops_cli.ui`)**: Corrected the Docker, telemetry, Valkey and review panels (#368), and made the dashboard quit promptly instead of hanging on an open log stream (#372).
- **Template Rendering (`devops_cli.core.templating`)**: Encoded values as JSON rather than pasting them between quotes, so a value containing a quote or newline cannot produce malformed output (#378).
- **Manifest Validation (`devops_cli.k8s`)**: Validated only actual manifests, discriminating on `apiVersion` rather than `kind`, and loosened an over-strict ArgoCD probe (#376).
- **Review Loop Calibration (`devops_cli.ai.review`)**: Grounded verification in tooling rather than model agreement -- a claimed `None` dereference is now settled by `mypy --strict`, a placeholder advisory identifier invalidates a dependency finding, and a claim against an uninstallable Python is rejected against `requires-python` (#349, #350, #371, #380).
- **Review Benchmarking Honesty (`devops_cli.ai.prompt_eval`)**: `devops ai prompt-eval` had reported accuracy 1.0 and a 0.0 false positive rate on every run without invoking a model. It now replays the deterministic suppression layer against recorded verdicts and reports both directions separately (#385).
- **AI Slot Leasing (`devops_cli.ai.client`)**: Removed arbitrary defaults from network slot leasing and raised file size limits to 50 MiB (#344, #345).
- **Continuous Integration Workflows**: Dropped an invalid `--depth=0` from devcontainer change detection (#355) and rebuilt the devcontainer image when the build workflow itself changes.

### Changed & Improved
- **HTTP Connection Reuse (`devops_cli.http.pool`)**: Shared pooled clients with HTTP/2 and bounded keepalive instead of constructing one per request -- 1.5x faster on a LAN endpoint, 4.1x on a WAN endpoint, and a proxied cluster request from 34ms to 13ms (#374).
- **In-Memory Ignore Evaluation (`devops_cli.core.gitignore`)**: Evaluated git ignore rules in-process against `pathspec`, including nested `.gitignore` files and `.git/info/exclude`, rather than spawning `git check-ignore` per file -- 39.5ms to 0.73ms per file, a 54x reduction (#373).
- **Merged Pull Request Sweeps (`devops_cli.github.issue_closure`)**: Read pull request bodies and issue states in a fixed number of calls rather than one subprocess each -- 170 subprocesses to 2, and 76s to 6.4s over 100 merged pull requests (#382).
- **Quality Gate Execution (`devops_cli.ci`)**: Parallelized the gate and narrowed test selection to the sources a change touches (#354).
- **AI Prompt Efficiency (`devops_cli.ai.tasks`)**: Compressed the two hot-path review prompts from 4785 to 3244 tokens with every decision rule preserved and pinned by tests, and scoped host-specific rules so they no longer apply when reviewing other repositories (#386).
- **Agent Instructions (`AGENTS.md`)**: Recorded that hard wrapping belongs in source files rather than emitted output (#384), and stated the token and inference cost of a `devops ai` call with a one-at-a-time concurrency cap (#390).
- **Roadmap**: Scheduled AI review verification integrity work (#360), OCI container image packaging and GHCR metadata (#333), and prompt benchmarking with synthetic corpora for evaluation and fuzzing (#387).

## [0.2.21] - 2026-09-19

### Added
- **Multi-Scale Semantic Outline & Inspectional Reading Scanner (`devops_cli.ai.inspect`)**:
  - Replaced monolithic file dumping with human-like inspectional reading and hierarchical perceptual scaffolding across 3 zoom levels: Topology, Structural Outline, and Deep Focal Window (`devops ai read --inspect`).
  - Added AST symbol extraction, hotspot complexity mapping, and dynamic focal window targeting.
- **Approximate Lifetime Spend Tracking & Observability (`devops_cli.ai.cost`)**:
  - Introduced persistent ACID SQLite ledger (`spend.db`) tracking request tokens, backend server endpoints, model names, durations, and approximate USD spend without blocking execution (`devops ai spend`, `devops ai cost report`).
  - Integrated model pricing dataset (LiteLLM registry) with parameter-bracket heuristics and custom overrides (`devops ai cost set-price`).
  - Exported Prometheus metrics (`/metrics`) and dedicated Grafana observability dashboard (`k8s/monitoring/dashboards/ai-spend.json`).
- **Priority Classification for AI/LLM Inference (`devops_cli.ai.gateway`, `devops_cli.ai.models`)**:
  - Implemented dynamic request classification prioritizing interactive/chat calls (`high`), pipeline tasks (`normal`), and background jobs (`as_available`).
  - Integrated client-side token governance and capacity-aware dispatch.
- **LightLLM & Portkey AI Routing Services Integration (`devops_cli.ai.gateway`, `devops_cli.ai.models`)**:
  - Expanded DevOps CLI AI routing tier to support Portkey AI Gateway on port 8787 and LightLLM TokenAttention inference engine on port 8000.
  - Implemented zero-trust perimeter policies, dynamic model route discovery, and direct backend health probing.
- **Dynamic Slot Leasing & Context-Aware File Review (`devops_cli.ai.client`, `devops_cli.ai.review`)**:
  - Dynamic least-loaded slot leasing across candidate inference servers with condition variable notifications.
  - Multi-layered file classification (shebangs, MIME types, AST parsing, canonical names) routing documentation, config, and code files to specialized review task prompts.
- **Milestone, Release Epics & Subsystem Research Synchronization (`devops_cli.github.release_epics`, `devops_cli.github.roadmap_sync`)**:
  - Added native Release Epics management engine (`devops release epic`) and FastMCP tool `release_epic_sync`.
  - Automated 20-deliverable issue synchronization for `v0.2.22` (#307–#326) with local task file generation in `docs/agent/tasks/`.
  - Replaced fragile multi-word bag overlap heuristics with strict deterministic title and issue number matching in roadmap sync.
  - Synchronized GitHub Projects v2 custom fields with client-side quota budgeting and rate-limit safety guards.

### Fixed & Hardened
- **Reliability Hardening, Exception Sanitization & Telemetry Optimization (`devops_cli.telemetry`, `devops_cli.core.exceptions`)**:
  - Hardened exception handling across AI, Git, Security, and Core modules with explicit domain exception hierarchies.
  - Enforced bounded string length caps ($\le 256$ chars) on external exception details to prevent log bloat and CWE-209/CWE-400 leakage.
  - Optimized OTel span processors and deduplicated telemetry attributes across command invocations.
  - Resolved Bandit B608 static finding in `SpendLedger` using parameterized SQLite queries.

## [0.2.20] - 2026-09-18

### Added
- **Forward-Looking Project Management & Automated Roadmap Synchronization (`devops_cli.github.projects`, `devops_cli.github.issues`)**:
  - Implemented forward-looking project management principles in `AGENTS.md` and automated roadmap synchronization (`devops gh issues sync-roadmap`) converting uncompleted roadmap deliverables into GitHub Issues and per-task tracking files (`docs/agent/tasks/`).
  - Hardened documentation compactor (`devops docs compact`) against truncating or removing scheduled milestones.
- **Automated Pull Request Synchronization & Branch Update Integrations (`devops_cli.github.pr_update`)**:
  - Implemented native CLI command `devops pr update` (with batch `--all`, optimistic concurrency `--expected-head-sha`, and `--dry-run`), FastMCP tool `pr_update_branch`, and GitHub Actions workflow `.github/workflows/update-prs.yml`.
- **Fast CI Execution Caching & Git Pre-Commit File Change Tracking (`devops_cli.commands.ci`)**:
  - Introduced input-addressed execution caching for `devops ci` quality gates, reducing unchanged verification from ~3 minutes to sub-second execution with Git working tree change tracking and `--no-cache`/`--force` overrides.
- **Universal Subcommand Option Propagation (`devops_cli.core.command_options`)**:
  - Ensured universal trailing `--dry-run` and `--explain` options across all CLI subcommands with declarative dry-run callbacks and option inheritance.

### Performance & Optimization
- **CI Performance Acceleration, Worker Auto-Scaling & Pathological Test Mocking (`devops_cli.commands.ci`)**:
  - Accelerated `devops ci` quality gate pipeline latency by over 75% with dynamic Pytest worker auto-scaling (`min(os.cpu_count(), 8)`).
  - Mocked unmocked socket probes in Kubernetes context bootstrapping, bounded `.venv` workspace traversal in repo map generation, and bypassed whole-tree git hashing in CI tests.
  - Eliminated sequential blocking documentation passes with zero-blocking concurrent pipeline dispatch at timestamp 0.

### Fixed & Hardened
- **Review Findings Remediation & Defensive Boundary Hardening (`devops_cli.ai.rag`, `devops_cli.sandbox`, `devops_cli.core.audit`)**:
  - Enforced path traversal guards (`validate_no_path_traversal`), forbidden system root blocks, symlink rejection, and pre-flight file size caps ($\le 5\text{MB}$) across RAG chunkers, drift analysis, benchmark chunkers, and prompt evaluation.
  - Decomposed complex workspace directory validation in sandbox engine into single-responsibility helpers, enforcing cyclomatic complexity $M \le 4$.
  - Enforced atomic serialized file exports (`write_serialized_file`) in Kubernetes diagnostics.
  - Hardened None-safe severity handling in review reporting and pipeline stages.
- **Review Verification Prompts & Closed-Loop Feedback Dataset Export (`devops_cli.ai.review`)**:
  - Hardened verification prompts (`verify_finding_system.md`) with falsification rules distinguishing internal loopback services, CLI path logging, and local scope variable grounding from false-positive vulnerabilities.
  - Updated DevSecOps persona instructions and expanded the anti-hallucination catalog (`common_hallucinations.json`).
  - Closed the self-improvement loop with automated dataset export (`devops review export-feedback --status ALL`) to `.data/feedback_dataset.jsonl`.
- **Review Markdown Code Block & Asterisk Formatting (`devops_cli.ai.review`)**:
  - Implemented line-start fence delimiter detection in fix and description formatters to prevent inline backticks (e.g. `print("```")`) from creating malformed Markdown fences.
  - Hardened title and heading rendering by escaping un-backticked asterisks (`\*`) to prevent Markdown bold collisions with Python unpacking syntax (`**kwargs`).
  - Conditioned Markdown bold stripping on matched outer pairs (`^\s*\*\*(.+)\*\*\s*$`), preserving valid variable names like `**kwargs`.
- **Dynamic Package Version Loader & Pyproject Single Source of Truth (`devops_cli.core.version`)**:
  - Refactored `devops_cli.__version__` to read directly from `pyproject.toml` metadata as the single source of truth.
  - Derived generator test fixtures dynamically from `devops_cli.__version__` to prevent stale version assertions.
- **PR Copilot Timeline State Parser Robustness (`devops_cli.github.pr_monitor`)**:
  - Safely handles JSON array timeline payloads and empty responses (`[]`) from `gh api .../timeline`, preventing `AttributeError: 'list' object has no attribute 'get'` during PR monitoring.

### Changed & Improved
- **Release v0.2.20 Branch Initialization**:
  - Created `release/v0.2.20` tracking branch, bumped package version to `0.2.20`, and synchronized documentation across the repository.

## [0.2.19] - 2026-09-16

### Added
- **Adaptive Embedding Batch Sizing Circuit Breaker & Valkey L2 Chunk Caching (`devops_cli.ai.rag.embeddings`)**:
  - Implemented dynamic batch sizing starting at 32 with automatic halving (32 -> 16 -> 8 -> 4 -> 2 -> 1) on latency degradation (> 2.0s) or timeouts.
  - Added recursive sub-batch subdivision and single-chunk request fallback when multi-chunk batches fail across candidate nodes.
  - Implemented exponential backoff with bounded jitter on transient network timeouts.
  - Integrated pre-flight Valkey SHA-256 chunk cache checks before remote embedding dispatch, with automatic write-through caching and 7-day TTL.
- **Automated Draft Release PR Description Generator (`devops release pr`)**:
  - Automatically queries and lists target milestone issues and deliverables under `### Target Milestone Deliverables`.
  - Dynamically synthesizes Gated CI quality checklists, CodeQL, and PR readiness controls adapted for draft vs. ready pull requests.
  - Resolves clean, non-duplicate release notes from git commits and changelog sources, preventing previous release note duplication.
- **Git Squash Merge Commit Body Parsing & Categorization (`devops release changelog`)**:
  - Parses squash commit bodies (`%B`) to extract PR commit items into Keep-a-Changelog sections (`### Added`, `### Fixed & Hardened`, `### Changed & Improved`).

### Performance & Optimization
- **Parallel Async Branch and PR Review Worker Pool with Semaphore Concurrency (`devops_cli.ai.review`)**:
  - Implemented `ReviewWorkerPool.create()` with bounded semaphore concurrency ($1 \le C \le 8$), token-bucket rate limiting (`DEFAULT_REVIEW_RATE_LIMIT = 10.0`), and per-task timeout management.
  - Upgraded pre-analysis refresh, multi-persona segment review, findings validation, and persona loops in both `ReviewPipelineOrchestrator` and `runner.py` to use managed asynchronous worker pools.
  - Replaced legacy unbound `ThreadPoolExecutor` and sequential single-worker fallbacks with concurrent execution, accelerating multi-file and multi-persona review cycles while preventing VRAM spikes, Ollama out-of-memory errors, and rate-limit throttling.
  - Hardened error isolation with `return_exceptions=True` across parallel review stages, guaranteeing that an isolated LLM inference error or malformed payload does not fail remaining segment reviews.

### Fixed & Hardened
- **GitHub Copilot Review Completion on Resolved Threads (`devops pr monitor`, `devops pr wait`)**:
  - Automatically transitions `copilot_status` to `completed` when all recommended changes in review threads have been addressed and 0 unresolved threads remain.
  - Prevents premature failure exit code 2 when all CI checks are green and all discussion threads have been resolved.
  - Excludes bot reviews from human review approval decision evaluations in `_resolve_review_decision`.
- **Main Branch AI Review & Base Resolution (`devops ai review branch`)**:
  - Dynamically resolves comparison bases when reviewing `main` branch or when passing `main` as an argument from another branch (e.g. `release/v0.2.19`).
  - Supports diffing uncommitted working tree modifications against `HEAD`, and cleanly falls back to latest release tags or parent commits (`main~1`) when working tree is clean.
  - Automatically switches comparison targets when positional branch argument matches default base on an active topic/release branch.
- **Documentation Compactor Idempotency (`devops docs compact`)**:
  - Enhanced version range regex to parse all matching version patterns from roadmap headers and recognize canonical summary blocks, guaranteeing idempotent compaction.
- **Polyglot Tree-Sitter File Size Boundary Guard & Resource Containment (`devops_cli.ai.repomap`)**:
  - Enforced pre-flight `MAX_REPOMAP_FILE_SIZE_BYTES` checks in `_polyglot_to_file_node` for all multilingual source trees (TypeScript, Go, Rust, Java, HCL), excluding files exceeding 5MB to prevent memory spikes and OOM crashes.
  - Hardened symlink resolution with `strict=True` to trap and exclude circular symlink loops (`ELOOP`) and symlinks escaping repository workspace boundaries.
  - Added structured warning logging on oversized file exclusions and symlink containment violations.
- **Pre-Release Non-Empty Changelog Verification (`devops release check`)**:
  - Enforced strict validation ensuring changelog notes are populated prior to release certification.

### Changed & Improved
- **AI/LLM Prompt Deduplication & Token Utilization Optimization**:
  - Authoritatively centralized anti-hallucination invariants into `src/devops_cli/ai/tasks/review.md`.
  - Removed duplicate multi-paragraph blocks across all 6 personas (`architect`, `auditor`, `challenger`, `devsecops`, `pm`, `qa`) and review task prompts.
  - Slashed prompt footprint by 32% (~1,500 tokens saved per review turn).
- **High-Performance AST Context Packer with Binary Search Truncation (`devops_cli.ai.context_packer`)**:
  - Replaced O(N^2) linear statement re-unparsing loops with O(log N) binary search truncation index discovery.
  - Implemented O(1) per-statement token weight estimation with AST node memoization (`_estimate_stmt_tokens`).
  - Added tokenizer pre-warming in `ContextPacker` initialization, dropping 1,000-line AST tree pruning latency from >300ms down to <5ms.
- **Release v0.2.19 Branch Initialization**:
  - Created `release/v0.2.19` tracking branch, bumped version to `0.2.19`, and synchronized documentation across the repository.


## [0.2.18] - 2026-09-16

### Added
- **Sigstore Cosign Container Provenance & Automated Keyless Signing (`devops docker sign`, `devops docker verify`)**:
  - Cryptographic container image signing and signature verification using Sigstore Cosign with Keyring-backed ephemeral OIDC tokens.
  - Automated pre-push artifact verification, GHCR registry cleanup, and zero-trust container supply chain security.
- **Kubernetes Falco eBPF Runtime Security Streaming & Anomaly Detection (`devops k8s security-stream`)**:
  - Real-time kernel eBPF runtime security event streaming, priority filtering, and automated anomaly classification via Falco sidecar.
  - Granular severity thresholding, JSON event ingestion, and terminal alerting for unexpected process execution, filesystem writes, and privilege escalations.
- **Distributed Threat Intelligence Valkey L2 Cache & Cloudflare Radar Batching (`devops security intel package`, `devops security intel network`)**:
  - Distributed threat intelligence evaluation pipeline with Valkey L2 caching, Cloudflare Radar batching, and OSV package vulnerability analysis.
  - Configurable TTL caching, offline-first fallback, and automated domain/package reputation scoring.
- **Multi-Tier Docker Sandbox Networking Options (`devops sandbox deploy --network-mode`)**:
  - Configurable sandbox network isolation modes: `isolated` (zero egress), `egress-only` (restricted outbound), and `host`.
  - Network policy verification, automated port mapping validation, and container egress containment.
- **Native GitHub API Rate Limiting & Token-Bucket Pacing (`devops gh api`, `devops gh rate-limit`)**:
  - Native client-side token-bucket rate limiter (`run_gh`, `GitHubRateLimiter`) with adaptive request throttling, low-quota circuit breakers, and read caching.
  - Automatic quota reset monitoring and elimination of bare unmanaged `gh` CLI invocations.

### Fixed & Hardened
- **Zero Information Leakage & Secret Sanitizer Hardening**:
  - Word-boundary regex enforcement for sensitive keys and tokens, eliminating partial-word false positives.
  - Comprehensive path exclusions preventing credential leakage in log streams and exception representations.
  - Concrete RFC 1918 and internal homelab hostnames replaced with RFC 5737 documentation placeholders across code, tests, and documentation.
- **Kubernetes Ollama Memory Uncapping & DaemonSet Limit Elevation**:
  - Uncapped Ollama container memory limits in Kubernetes manifests to prevent OOM kills on high-parameter models.
  - Elevated CoreDNS and daemonset resource allocations for high-throughput cluster environments.
- **Mandatory Draft PR Policy & Pre-Push Quality Gate Enforcement**:
  - Defaulted release pull requests to draft mode (`devops release pr --draft`) to guarantee review controls.
  - Enforced mandatory pre-push local `devops ci` gate via pre-commit hooks, guaranteeing 100% test passing and >= 90% code coverage.
- **DevSecOps Review Feedback Remediation**:
  - Remediated review findings across sandbox container streaming, path traversal mitigations, and mock provider locations.

## [0.2.17] - 2026-09-14

### Added
- **Protocol-Agnostic Endpoint Readiness & Health Probing Subsystem (`devops sandbox probe`)**:
  - Multi-protocol health verification supporting HTTP/HTTPS, TCP socket handshakes, UDP datagram echoes, and TLS certificate validation.
  - Granular bounded timeouts, adaptive retry policies, and structured exit reporting for container startup orchestration.
- **Cgroup v2 Metrics Collection & Prometheus Application Scraping (`devops sandbox metrics`)**:
  - Native Linux cgroup v2 hierarchy traversal for memory limits, CPU throttle statistics, swap usage, and I/O pressure metrics (`psi/`).
  - Prometheus exposition format client scraping and real-time terminal metrics reporting.
- **W3C Traceparent Propagation & Distributed Trace Correlation (`devops sandbox traces`)**:
  - Distributed trace context injection and extraction conforming to W3C Trace Context specifications (`traceparent`, `tracestate`).
  - Terminal waterfall timeline rendering for span durations, network latencies, and child context propagation.
- **Streaming Diagnostic Log Aggregator & Panic Detector (`devops sandbox logs`)**:
  - Real-time multiplexed container log tailing with regex-driven panic, deadlock, and unhandled exception detection.
  - Color-coded severity categorizations and automated crash context diagnostics.
- **Automated GitOps Drift Detection & Argo CD Watch (`devops argo gitops watch`)**:
  - Automated continuous GitOps reconciliation and drift detection against remote Git repositories and target cluster states.
  - Rich status dashboard and automatic event notifications for out-of-sync or degraded Argo CD applications.
- **Declarative GitHub Branch Protection Ruleset Auditor & Synchronizer (`devops gh branch-protection`)**:
  - Declarative policy specification in YAML (`.github/branch-protection.yml`) for `main` and `release/*`.
  - Comprehensive drift detection across required reviews, status checks, admin enforcement, and merge restrictions, with automated sync.
- **Libsodium-Sealed Repository Secrets Synchronization (`devops gh secrets`)**:
  - Secure public-key encryption using PyNaCl libsodium sealed-boxes for GitHub Actions repository secrets.
  - Direct synchronization from OS Keyring or HashiCorp Vault with strict zero-plaintext-leakage guarantees and bounded error truncation.
- **Deterministic Async Memory & Connection Pool Profiler (`devops test profile-memory`)**:
  - Leverages Python `tracemalloc` to snapshot, measure, and analyze heap allocations and detect socket leaks across async workloads (`fastmcp`, `http-pool`, custom callables).
  - Configurable peak memory thresholds (`--max-peak-mb`), socket leak validation (`--fail-on-leak`), OpenTelemetry span profiling, and structured JSON output.
- **DevOps CLI GitHub Operations & Pull Request Governance (`devops gh`, `devops pr`)**:
  - Native Typer command groups for GitHub Projects v2, milestones, labels, issues, and PR lifecycle management.
  - Multi-tiered merge readiness gating requiring 0 merge conflicts, 0 unresolved review threads, green CI checks, and approved reviews.
  - Resilient GitHub GraphQL secondary rate limit detection and automatic REST API fallback.
  - Programmatic review thread resolution (`devops pr threads resolve-all`) and replied-thread validation (`--auto-resolve`, `--allow-replied-threads`) in merge readiness checks.
- **Mandatory Draft PRs for In-Progress Work**:
  - Enforced policy and tooling requiring in-progress work to start as draft pull requests, preventing premature reviews and merge attempts.
- **Automated CI Check & Review Thread Monitoring (`devops pr monitor`, `devops pr checks`)**:
  - Real-time polling and progress inspection of remote CI checks, Copilot code reviews, and unresolved conversation threads.

### Fixed & Hardened
- **Kubernetes & Cloud Native Hardening**:
  - Resolved Helm Server-Side Apply (SSA) field ownership conflicts, Loki validation errors, and PodSecurity compliance issues (`k8s/`).
  - Centralized Fluent Bit namespace scoping and log perimeter hardening (`k8s/logging/`).
  - Flexible Kubernetes context configuration and conditional Minikube autostart.
- **DevSecOps Review Feedback Loop & Anti-Hallucination Datasets**:
  - Closed-loop review remediation and test verification across all static analysis and security scanning rules.
  - Updated anti-hallucination datasets for AI review models.
- **Core Dependency Ecosystem Alignment**:
  - Synchronized and locked dependencies across `uv.lock` for Python 3.14+ runtime stability.

## [0.2.16] - 2026-09-12

### Added
- **Long-Running Workload Sandbox Lifecycle Engine (`devops sandbox`)**:
  - Secure ephemeral Docker container sandboxes for long-running processes, dev servers, background tasks, and isolation testing.
  - Lifecycle orchestration: `deploy`, `status`, `exec`, and `stop`.
  - Enforced memory limits, CPU bounds, read-only root filesystems, and bounded workspace mounts.
- **Automated Formatting and Linting Commands (`devops format`, `devops lint`)**:
  - Introduced top-level `devops format` and `devops lint` CLI commands with clean leaf command usage.
  - Default `--fix` enabled across `devops ci`, `devops ci format`, and `devops ci lint`, with `--check` flag for non-mutating validation.
  - Reorganized Jekyll documentation site under `docs/` for seamless GitHub Pages rendering.
- **Squid Caching Forward Proxy & SSL-Bump Cluster Enablement (`k8s/squid/`)**:
  - Deployed Squid caching forward proxy in Minikube/Kubernetes cluster with SSL-Bump decryption, local CA generation (`devops tls generate-ca`), and signed endpoint certificates (`devops tls generate-cert`).
  - Enabled proxy cluster-wide, resolving root CA trust and accelerating external LLM model downloads and container registry image pulls.
  - Comprehensive Prometheus metrics scraping and automated health failover handling.
- **Context Document Compaction Engine (`devops docs compact`)**:
  - Context-preserving document compaction CLI and engine designed for large AI prompts, runbooks, and historical task tracking archives.
  - Compaction options including token estimation, hierarchical section reduction, and technical invariant preservation.
- **AI Chat Rich Formatting & Persona Styling**:
  - Modernized interactive `devops ai chat` CLI with live Rich Markdown streaming, syntax-highlighted code blocks, and formatted thinking display blocks.
  - Integrated distinct Persona Orange visual styling for enhanced developer identity.
- **Pre-1.0 Alpha Policy & Post-1.0 SemVer Governance**:
  - Formalized Pre-1.0 Alpha lifecycle policy guaranteeing zero backwards compatibility prior to 1.0.0 and requiring ruthless elimination of legacy remnants, obsolete shims, and zombie code.
  - Defined strict Semantic Versioning 2.0.0 and enterprise change management guidelines for post-1.0 releases.
- **Roadmap Strategic Expansion**:
  - Added Core Principles 12-14 and scheduled milestones:
    - **v0.2.19**: *Autonomous Trial-and-Error Solution Discovery, MCTS Exploration & Delta-Debugging Engine*
    - **v0.2.20**: *Deep Cognitive Information Foraging, Syntopical Reading & Epistemic Research Engine*
    - **v0.2.21**: *Iterative Agentic GitHub Project Manager & Autonomous Backlog Orchestration*

### Fixed & Hardened
- **Release Notes Fallback Extraction & Fatal Changelog Check (`devops release notes`, `devops release check`)**:
  - Strictly enforce matching version in `CHANGELOG.md` during `devops release check`, failing with exit code 1 if missing or mismatched.
  - Layered fallback extraction across `CHANGELOG.md` -> `docs/RELEASE_NOTES.md` -> git commit history (`git log <prev_tag>..HEAD` or `git log -n 20`).
  - Guarded `.github/workflows/release.yml` with a defensive fallback to commit logs in the release notes extraction step.
  - Decomposed `release_check` into helper functions preserving cyclomatic complexity <= 10.
- **DevSecOps Review Findings Remediation**:
  - **Credential Leakage Defenses**: Excluded `authorization_token` from serialized model settings in diagnostics while preserving runtime provider authentication in MCP tools (`NativeTool.get_model_settings`, `_build_mcp_tool_settings`).
  - **Argument & Command Injection Mitigation**: Centralized Kubernetes RFC 1123 resource name validation in `core/validation.py` for chaos testing (`k8s/chaos.py`) and log querying (`k8s/logql.py`).
  - **Rich Markup Injection Defense**: Hardened `console.print()`, `panels.py`, `scalars.py`, and `table_builder.py` with `safe=True` markup escaping to prevent terminal escape injection.
  - **WebSocket Frame Bounding**: Enforced 1MB maximum frame size at raw UTF-8 byte level in `server/routes/stream.py`, closing oversized connections with code 1009.
  - **Error String Bounding**: Enforced strict <= 256 character limits on exception messages in `pipeline/pipeline.py` and dry-run details to prevent log injection.
  - **Offline Threat Intel Fallback**: Integrated resilient offline fallbacks into `security/reference_extractor.py` and filtered documented example domains (RFC 2606, 6761), IPs (RFC 5737, 3849, 6890), and telephone numbers.
  - **Closed-Loop Feedback**: Registered `HALLUCINATION-LOCAL-FILE-OR-COLLECTION-CWE400` in common hallucinations catalog and added falsification rules in review prompts.
- **Comprehensive Infrastructure & Homelab Sanitization**:
  - Stripped internal LAN hostnames, RFC 1918 IPs, concrete hardware mount paths, and homelab topology across codebase templates, manifests, tests, and documentation.
  - Hardened agent instructions in `AGENTS.md` and `instruction_generator.py` to enforce abstract infrastructure placeholders (`<storage-node>`, `<host>`, RFC 5737 documentation blocks).
  - Protected local user runtime `config.yaml` from automated sanitization resets.
- **Kubernetes Workload Resource Tuning & OOMKill Prevention**:
  - Eliminated container cgroup OOMKills (`ExitCode 137`) across Jaeger and Valkey workloads by adjusting memory requests/limits and bounding trace/key buffers.
- **Architectural Circular Import Decoupling**:
  - Decoupled circular module imports and streamlined convoluted import patterns across core config settings, CLI main entry points, and stack lifecycle runners.
- **Unified Embedding Configuration**:
  - Consolidated all embedding configuration under `ai.tasks.embedding` (`model`, `ollama_urls`, `timeout`), removing duplicate and conflicting keys under `ai.rag`.

## [0.2.15] - 2026-09-10

### Added
- **Centralized Kubernetes Logging Stack & LogQL Integration (`devops k8s logs`)**:
  - Loki log aggregation engine and Fluent Bit log forwarder integration with dynamic namespace scraping.
  - Invocation `devops k8s logs [--query <logql>] [--tail <n>] [--follow] [<pod_name>]` supporting LogQL expressions, label streams, stream filtering, and JSON/terminal output formatting.
  - FastMCP tools for Loki centralized log exploration.
- **Infracost FinOps Cloud Cost Engine (`devops tf cost`)**:
  - Cloud infrastructure cost estimation and breakdown across AWS, Azure, and Google Cloud with breakdown tables and diff reporting.
- **Multi-Cluster ArgoCD Fleet Sync & Rollouts (`devops argo sync --fleet`)**:
  - Multi-cluster ArgoCD orchestration, fleet synchronization across managed clusters, and automated rollback triggers on health degradation.
- **BaseSecurityScanner Registry Migration**:
  - Completed migration of all 11 built-in security scanners (Bandit, Checkov, Dive, Gitleaks, Kubeconform, Kube-linter, Pluto, Popeye, Semgrep, TFLint, Trivy) to `BaseSecurityScanner` and unified `ScannerRegistry`.
- **Target-Agnostic AI Code Review & Multi-Convention Discovery**:
  - Generalize `devops ai review` for arbitrary target repositories (Python, Go, Rust, TypeScript, monorepos, Kubernetes manifests) with automated discovery across `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursorrules`.
- **Modular Agent Task Architecture (`docs/agent/tasks/`)**:
  - Per-task markdown tracking eliminating git merge conflicts across feature branches.

### Fixed
- **Distributed Tracing & Jaeger Stability Optimizations**:
  - Reduced `MEMORY_MAX_TRACES` to 10,000 and increased memory limit to 1024Mi in `k8s/otel/jaeger.yaml` to prevent pod OOMKills (`Exit Code 137`).
  - Refactored `src/devops_cli/telemetry/tracer.py` to avoid recording stack trace events on handled CLI exits (`typer.Exit`).
  - Bounded embedding timeout (`DEFAULT_RAG_EMBEDDING_TIMEOUT: 15.0`) with 2.0s connect timeout in `src/devops_cli/ai/rag/embeddings.py` for rapid multi-node failover.
- **Compatibility Remnants & Zombie Code Removal**:
  - Eliminated obsolete fallback shims, proxy wrappers, and vestigial aliases project-wide.

## [0.2.14] - 2026-09-09

### Added
- **Tree-Sitter Multilingual AST Graph & Polyglot Code Intelligence Engine (`devops ai ast`, `devops ai repomap --multilingual`)**:
  - Polyglot concrete syntax tree (CST) parser and S-expression query engine supporting Python, TypeScript, Go, Rust, Java, and HCL/Terraform without requiring host C compiler toolchains.
  - Subcommands `devops ai ast parse <file> [--query <s-expr>]` and `devops ai ast graph <path> [--format json|dot]`.
  - FastMCP tools `ai_ast_parse` and `ai_ast_graph` with dynamic AST schema exports.
  - Resilient zero-crash fallback to standard library `ast` when optional tree-sitter grammars are uninstalled.
- **Library API Drift & Deprecation Usage Auditor (`devops ai audit-library-usage`)**:
  - Proactive AST call-site auditor comparing workspace code against indexed library contracts in `.data/libraries/`.
  - Categorizes and flags `REMOVED_METHOD`, `UNKNOWN_ATTRIBUTE`, `UNRECOGNIZED_KWARG`, and `DEPRECATED_CALL`.
  - Emits Rich terminal discrepancy tables and persistent JSON reports (`.data/analysis/api_drift_report.json`) with `--fail-on-breaking`.
- **AI Context Packing & Symbol-Pruned Prompt Synthesizer (`devops ai pack-context`)**:
  - AST-driven symbol extraction and usage ranking reducing prompt token consumption by 40-60% while preserving strict interface fidelity.
  - Strips unreferenced private functions, methods, and attributes (`_helper`), skeletonizes function bodies with ellipsis (`...`), and compresses docstrings.
  - Multi-snippet token budgeting (`pack_snippets`) distributing limits proportionally across files.
  - Integrated into AI review pipeline `Stage1PreAnalysis` replacing naive character slicing.
  - CLI command `devops ai pack-context <path> [--referenced <syms>] [--max-tokens <int>]` and FastMCP tool `ai_pack_context`.
- **Autonomous RAG Index Drift Detection & Auto-Reindexing Engine (`devops ai rag drift`)**:
  - Compares working tree file content hashes and git commit HEAD divergence against vector index cache (`WorkspaceIndexer._load_cache()`).
  - Tracks `stale_modified_files`, `new_unindexed_files`, `deleted_files`, and computes normalized drift score ($[0.0, 1.0]$).
  - OpenTelemetry distributed tracing span (`rag.drift_detection`) and Prometheus metrics (`devops_cli_rag_drift_detected_total`, `devops_cli_rag_drift_score`).
  - Automated index reconciliation via `--auto-sync` and exit code gating with `--fail-on-drift`.
  - FastMCP tool `rag_drift(path, auto_sync)`.
- **Import-Driven AST Prompt Grounding & Contract Invalidation**:
  - Ground-truth library contract injection into code review stages (`Stage1PreAnalysis` and `Stage3PersonaReview`), reducing third-party API hallucination rates to <1%.
- **FastMCP Library Intelligence Tools & Dynamic System Resources**:
  - 3 FastMCP tools (`ai_ingest_library`, `ai_query_library`, `ai_inspect_symbol`) and dynamic system resource `resource://libraries/indexed`.
- **Dynamic Package Introspection & Multi-Source Documentation Ingestion (`devops ai ingest`)**:
  - Automated type stub extractor indexing installed library signatures into structured Pydantic v2 contracts (`.data/libraries/<pkg>-contract.json`).
  - SSRF-guarded documentation crawler ingesting remote/local documentation with breadcrumb navigation.
  - Dedicated vector collection `devops_libraries` in Qdrant with Valkey symbol caching.
- **GitHub Pages, Issues, Projects & Views Integration with FastMCP**:
  - Complete management subsystem for GitHub Pages, Issues, Projects v2, and Views with 10 FastMCP tools and 4 dynamic system resources (`resource://gh/*`).
- **GitHub Pull Request Review Threads & Multi-Turn Conversation Management**:
  - Programmatic resolution and in-thread reply automation for GitHub Pull Request review threads via GraphQL and REST APIs.

### Changed
- **Knowledge Base & Documentation Freshness**: Introspected CLI reference and README command matrix with 117 registered FastMCP tool schemas.
- **Architectural Invariants Compliance**: Enforced strict cyclomatic complexity $\le 10$ and nesting depth $\le 5$ project-wide across all new modules and CLI commands.

## [0.2.13] - 2026-09-09

### Added
- **Sub-Agent Local Offloading Engine & Agent Harness Slots (`devops_cli.ai.harness.slots`)**:
  - Modular Harness Slots (`ModelSlot`, `SkillSlot`, `ToolSlot`, `SubAgentSlot`) offloading token-intensive AST exploration, file scouting, and symbol cataloging to local open models (Granite, Qwen2.5-Coder via Ollama).
  - "Big decides, small types, big checks" multi-tier synthesis protocol achieving 85%+ frontier token savings with automated baseline calculation.
  - Dedicated CLI command group `devops ai harness` (`status`, `offload`, `run`) with `--format json` and `--dry-run` modes.
  - 2 FastMCP tools: `ai_harness_status` and `ai_subagent_offload`.
- **Interactive Terminal UI Dashboard (`devops dashboard` / `devops tui`)**: Full-screen responsive terminal dashboard powered by `Textual` for live Kubernetes pods, Docker containers, OTel spans, Valkey cache metrics, and AI review statuses with keyboard navigation and accessible help modal.
- **Model Dependency Chaos Engineering Suite (`devops ai chaos-model`)**:
  - Automated fault injection engine (`ModelChaosInjector`) evaluating resilient fallback routing across 4 failure modes: artificial latency, HTTP 429 rate-limiting, request timeouts, and malformed JSON payloads.
  - Automated local open-model fallback routing ensuring CI quality gates pass without manual intervention.
  - OpenTelemetry spans and Prometheus counter metrics tracking chaos injections and recovery events.
  - FastMCP tool `ai_chaos_model` and CLI command `devops ai chaos-model`.
- **Agent Constellation Quiesce & Emergency Failover Controller (`devops ai quiesce`, `devops ai failover`)**:
  - Enterprise state machine managing agent constellation suspension (`quiesce`), emergency route diversion (`failover`), and state resumption (`resume`).
  - Persistent snapshot state machine in `.data/agent/quiesce.json` with active route discovery and health inspection.
  - 4 FastMCP tools: `ai_quiesce`, `ai_failover`, `ai_resume`, `ai_constellation_status` and live resource `resource://ai/constellation`.
- **Multi-Model LLM Benchmark Evaluation Harness (`devops ai benchmark --suite`)**:
  - Parallel evaluation runner executing standardized benchmark suites with quantitative scoring (precision, recall, F1, hallucination rate, throughput).
  - Rich leaderboard table output and Markdown export for offline analysis.
  - FastMCP tool `benchmark_suite`.
- **Parallel Async Multi-File Review Worker Pool & Streaming Diff Parser**:
  - Asynchronous worker pool (`ReviewWorkerPool`) leveraging Python 3.14 `asyncio.TaskGroup`, `asyncio.Semaphore`, and token bucket rate limiting.
  - Streaming generator-based unified diff chunker (`diff_stream_chunks`) for zero-copy review processing.
  - CLI flags `--concurrency` / `-c` and `--parallel / --no-parallel` across `devops review path`, `branch`, and `pr`.
- **Logfire Structured AI Observability Bridge (`logfire`)**:
  - Native integration with Pydantic Logfire (`LogfireBridge`) supporting bidirectional W3C traceparent propagation and OTel collector forwarding.
  - Context manager `logfire_agent_turn` and Rich terminal visualizers (`render_agent_turn_table`, `render_agent_turn_panel`).
  - FastMCP tool `telemetry_logfire_status` and dynamic system resource `resource://telemetry/logfire`.
- **In-Cluster Container Registry & Kubernetes Stack Lifecycle**:
  - Automated local container registry on NodePort `30500` with containerd mirror endpoints on k3s nodes.
  - PodSecurity admission label alignment across namespaces.
  - Added `--wait / --no-wait` and `--timeout` flags to `devops k8s deploy-stack` for non-blocking deployments.
- **GitHub Milestones Lifecycle Automation**: Hardened `close_repository_milestone` and `edit_milestone` with automatic title fallback and parameter signature inspection.

### Changed
- **Dependabot Active Release Tracking**: Configured `.github/dependabot.yml` to target active release branch `release/v0.2.13`.
- **Human-Readable Output Duration Formatting**: Rounded durations >= 10s to whole seconds across CLI outputs, benchmarks, and multi-stage reviews.
- **Configuration Deduplication & Child Path Rebasing**: Harmonized `append_cache` between `AIConfig` and `AICacheConfig`, and implemented table-driven child path rebasing in `DataConfig`.

### Fixed
- **Review Findings Remediation & Self-Improvement Loop Hardening**:
  - Automatically mask sensitive dictionary fields in root `DevOpsError` exception representations.
  - Hardened AI agent step persistence, durable execution serialization, prompt template sanitization against tag injection, and tool argument traversal checks.
  - Eliminated Bandit B104 hardcoded loopback binding alert and satisfied strict static type constraints in `test_gen.py`.
  - Expanded the common AI hallucinations catalog and deterministic pre-verification engine with checks for uninitialized variables above loops, Pathlib `resolve()` non-existent path behavior, health probe version disclosure, and SSE streaming event timestamps.
  - Expanded test coverage across GitHub projects, milestones, labels, and verification heuristics to exceed strict 90% quality gate.
- **DevContainer SSH Signing Key Isolation & Tooling**:
  - Isolated git commit signing to devcontainer without mutating user global configurations.
  - Installed `pre-commit` at the system level in devcontainer Dockerfile.
- **GitHub Pages Site Layout & Documentation Badges**:
  - Resolved table rendering for Kramdown, updated canonical repository links, and hardened responsive CSS layouts.
  - Addressed Copilot code review feedback with dynamic site versioning and defensive DOM helpers.

## [0.2.12] - 2026-09-07

### Added
- **Valkey Workstation Management & High-Performance Distributed Caching Tier (`devops valkey`)**:
  - Pure-Python synchronous RESP2/RESP3 wire protocol encoder (`encode_command`) and streaming parser (`parse_resp`) without native C dependencies (`src/devops_cli/valkey/protocol.py`).
  - Standard TCP socket client (`ValkeyClient`) with connection pooling, bounded timeouts, password authentication, and zero-trust SSRF destination validation (`src/devops_cli/valkey/client.py`).
  - Valkey-backed atomic sliding-window token bucket rate limiter (`ValkeyTokenBucketRateLimiter`) with fail-soft burst mitigation and embedded Lua evaluation script (`src/devops_cli/valkey/rate_limiter.py`).
  - Distributed AI embedding and review finding cache tier (`ValkeyCacheProvider`) with fail-soft availability semantics and automatic key namespace isolation (`src/devops_cli/ai/cache/valkey_cache.py`).
  - Dedicated CLI command group `devops valkey` with subcommands: `ping`, `info`, `stats`, `keys`, `get`, `set`, `flush`, `backup`, and `cli`, integrated with `@dry_run_command` and runtime duration formatting (`src/devops_cli/commands/valkey.py`).
  - 6 new FastMCP tools (`valkey_ping`, `valkey_info`, `valkey_stats`, `valkey_get`, `valkey_set`, `valkey_flush`) and live system resource `resource://valkey/status` (`src/devops_cli/ai/mcp/server.py`).
  - Configuration and Keyring integration for Valkey: host, port, DB, timeout, and secret password (`valkey.password`) in OS keyring.
- **GitHub Projects v2, Milestones & Runtime Duration Formatting**:
  - Human-readable duration formatting (`format_duration`) across all CLI command outputs, benchmarks, and multi-stage review pipelines.
  - Omitted status suffixes from milestone descriptions during automated roadmap extraction.
  - Automated project management FastMCP tools and GraphQL conversation resolution for Pull Request reviews.

### Fixed
- **OS Keyring Secret Health Auditor**:
  - Expanded audited secret keys in `devops config audit-keys` to 8 managed credentials including `valkey.password`.
- **Egress & Protocol Safety**:
  - Strict rejection of cloud metadata (`169.254.169.254`) and unauthorized non-public IPs on Valkey socket endpoints.

## [0.2.11] - 2026-09-06

### Added
- **DevSecOps Architectural Hardening & Zero-Trust Defense-in-Depth**:
  - Expanded universal secret sanitizer pattern catalog with HashiCorp Vault tokens (`s.*`, `hvs.*`, `hvb.*`), GitLab PATs (`glpat-*`), Slack webhooks, and HuggingFace API tokens (`hf_*`).
  - Injected `Authorization: Bearer <key>` into `OpenAIProvider` and `x-api-key` into `AnthropicProvider` with OS Keyring and environment variable fallbacks.
  - Implemented fail-closed SSRF DNS resolution guard in `_enforce_non_private_ssrf`, eliminating DNS-rebinding and unresolvable destination bypasses when `allow_private=False`.
  - Hardened Docker workload sandbox (`WorkloadSandboxRunner`) with default `read_only=True`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `pids_limit=256`, path containment blocking `~`, `.ssh`, `.aws`, `.kube`, `.git`, and `docker.sock`, and bounded subprocess timeouts.
  - Added `ignore_tests` parameter to `run_gitleaks_scan` and review static analysis stages to eliminate false alerts from mock test credentials per `AGENTS.md` guidelines.
  - Added Pod Security Admission (`restricted` / `baseline`) labels to `k8s/namespaces.yaml` and `k8s/llm/namespace.yaml`.
  - Created `k8s/llm/networkpolicy.yaml` with default-deny perimeter, intra-namespace routing, CoreDNS (port 53), and cloud metadata (`169.254.169.254/32`) egress blocking.
  - Configured restricted `securityContext` and `podSecurityContext` in `k8s/llm/values-qdrant.yaml`.
  - Pinned `uv` to `0.12.3` in `.devcontainer/Dockerfile`.
- **GitHub Integration Subsystem (`devops gh`)**:
  - Declarative label management (`devops gh labels sync`, `devops gh labels audit`) using `.github/labels.yml`.
  - Roadmap-driven milestone synchronization (`devops gh milestones sync`, `devops gh milestones list`).
  - GitHub Projects v2 lifecycle & template provisioning (`devops gh project sync`, `devops gh views list`).
  - Registered 6 new FastMCP tools for GitHub automation.
- **Architectural & Submodule Boilerplate Consolidation**:
  - Declarative `@dry_run_command` and `@cli_command_handler` decorators across CLI command modules.
  - Unified path containment helpers (`safe_resolve_subpath`), subprocess execution (`run_json_subprocess`), and binary checking (`require_binary`).
  - Consolidated security scanner base (`BaseSecurityScanner`, `ScannerRegistry`) and unified AST cache (`ASTCache`).
  - Table rendering helper (`render_table`, `TableBuilder`).

### Changed
- **Token Efficiency & Documentation Optimization**:
  - Streamlined `AGENTS.md` by 36% (10.5KB reduction) to resolve assistant context window truncation.
  - Deduplicated AI review prompt stack across `review.md`, `guardrails_isolation.md`, and `verify_finding_system.md` (34% token reduction per review segment).
  - Clarified workspace data tier (`.data`) versus dedicated agent work product tier (`.data/agent`).

## [0.2.10] - 2026-09-05


### Added
- **Native Pydantic AI Framework Subsystem Adoption**:
  - Adopted native `pydantic_ai.toolsets` (`AbstractToolset`, `FunctionToolset`, `create_function_toolset`, combinators) with dual sync/async contracts, replacing legacy custom toolsets in `src/devops_cli/ai/toolsets/`.
  - Adopted native `pydantic_ai.tools` (`Tool`, `ToolDefinition`, `DeferredToolRequests`, `ToolApproved`, `ToolDenied`) in `src/devops_cli/ai/tools/`.
  - Adopted native `pydantic_ai.template` (`TemplateStr`, `PromptTemplate`, `PromptRunner`) in `src/devops_cli/ai/template/`.
  - Adopted native `pydantic_ai.settings` (`ModelSettings`) and model modernizations in `src/devops_cli/ai/settings/`.
  - Adopted native `pydantic_ai.run` (`format_run_summary`, `create_pending_message`, traceparent header integration) in `src/devops_cli/ai/run/`.
  - Adopted native `pydantic_ai.retries` (`RetryClient`, `create_retry_transport`) in `src/devops_cli/ai/retries/`.
  - Adopted native `pydantic_ai.result` (`Usage`, `AgentRunResult`, `CostSummary`) in `src/devops_cli/ai/result/`.
  - Adopted native `pydantic_ai.profiles` and `pydantic_ai.providers` (`create_pydantic_ai_provider`, `ThinkingStreamProcessor` dynamic delimiters) in `src/devops_cli/ai/profiles/` and `providers/`.
  - Adopted native `pydantic_ai.output` (`ToolOutput`, `NativeOutput`, `PromptedOutput`, `TextOutput`, `StructuredDict`, `CallableDict`, `OutputSpec`) in `src/devops_cli/ai/output/`.
  - Adopted native `pydantic_ai.models.ollama` (`OllamaModel`, `create_ollama_model`, `create_ollama_provider`, profile overrides) in `src/devops_cli/ai/models/ollama.py`.
  - Adopted native `pydantic_ai.mcp` (`MCPToolset`, `create_devops_mcp_toolset`, dynamic in-process FastMCP discovery) in `src/devops_cli/ai/mcp/`.
  - Adopted native `pydantic_ai.function_signature` (`FunctionSignature`, `signature_from_schema`, `signature_from_callable`, `render_tool_interface`) in `src/devops_cli/ai/function_signature.py`.
  - Adopted native `pydantic_ai.format_prompt` (`format_as_xml`, `format_context_as_xml`, `format_findings_as_xml`) in `src/devops_cli/ai/format_prompt.py`.
  - Adopted native `pydantic_ai.exceptions` and unified domain error taxonomy in `src/devops_cli/ai/exceptions.py`.
  - Adopted native `pydantic_ai.durable_exec` (`DurableWorkflowEngine`, `WorkflowStepRecord`) in `src/devops_cli/ai/durable.py`.
  - Adopted native `pydantic_ai.direct` (`direct_request`, `direct_request_stream`) in `src/devops_cli/ai/direct.py`.
  - Adopted native `pydantic_ai.concurrency` (`ConcurrencyLimitedModel`, `ConcurrencyLimiter`) in `src/devops_cli/ai/concurrency.py`.
  - Re-exported native common tools (`web_fetch_tool`, `duckduckgo_search_tool`, `tavily_search_tool`, `exa_search_tool`, `image_generation_tool`, `x_search_tool`) with SSRF guardrails in `src/devops_cli/ai/common_tools.py`.
- **Autonomous Common Hallucinations Registry & Hardened Matching Engine**:
  - Centralized declarative hallucination catalog (`.data/common_hallucinations.json` and `src/devops_cli/ai/review/common_hallucinations.json`) tracking recurring false positives.
  - Category-aligned similarity guards preventing syntax rules from over-matching security findings (path traversal, SSRF, command injection).
  - Stop-words filtering in `_FORBIDDEN_COMMON_WORDS` to prevent generic words from contaminating signature keywords.
  - Ground-truth verification (`verify_ground_truth_hallucination`) before invalidating findings.
- **Dedicated Agent Operational Task Tracking**:
  - Relocated continuous, real-time agent task tracking to `docs/agent/task.md` with `docs/agent/README.md` governance.

### Changed
- **Persona & System Review Prompts**:
  - Added Python 3.14+ PEP 758 bracketless multi-exception syntax awareness (`except Exc1, Exc2:`) and sanitization placeholder guidance (`<masked-*>`, `[REDACTED]`) to `devsecops/prompt.md`, `architect/prompt.md`, and `verify_finding_system.md`.
  - Added explicit invalidation rules disallowing false alarms on valid variable identifiers (e.g. `secret_storage_failed`).
- **Elimination of Legacy Boilerplate & Zombie Code**:
  - Cleaned up custom implementations of toolsets and tools in favor of native Pydantic AI primitives.

### Security
- **Secret Sanitizer Regex Hardening (`src/devops_cli/ai/review/sanitization.py`)**:
  - Required assignment/token context to prevent redacting standard Python identifiers like `secret_storage_failed`.
- **Codebase Security Remediations (Review Session 141532)**:
  - `src/devops_cli/ai/ext_langchain.py`: Added percent-decoding `unquote` before path traversal checks.
  - `src/devops_cli/ai/agents/media.py`: Added 64-character hex regex validation and directory containment in `DiskMediaStore`.
  - `src/devops_cli/security/vault_broker.py`: Added percent-decoding `unquote` in `parse_vault_uri`.
  - `src/devops_cli/ai/review/auto_fix.py`: Added path containment check before writing candidate remediation branches.
  - `src/devops_cli/ai/common_tools.py` & `src/devops_cli/ai/agents/capabilities.py`: Reordered `blocked_domains` check before allowlists and SSRF DNS, added case-insensitivity and strict redirect SSRF validation, and forwarded `blocked_domains` from `WebFetch`.
  - `src/devops_cli/k8s/chaos_runner.py`: Validated arguments against CLI flag injection (`-` prefix) and inserted `--` into `kubectl delete pod`.
  - `src/devops_cli/ai/diff/difftastic.py`: Validated branch and base references against leading hyphens.
  - `src/devops_cli/security/complexity.py` & `src/devops_cli/security/kubelinter.py`: Relativized target file paths to prevent system path disclosure.

## [0.2.9] - 2026-09-03

### Added
- **Deterministic Prompt Rule Transformations & Location Canonicalization (`src/devops_cli/ai/review_schema.py`, `tests/test_prompt_programmatic_functions.py`)**:
  - Added pure programmatic functions replacing fragile inline LLM prompt heuristics: `canonicalize_finding_location` (canonical `file:start-end` or `file:line` formatting, markdown reference stripping, inverted range correction), `sanitize_finding_text` (stripping criteria leakage and prompt boilerplate), and `derive_recommendation` (severity-based merge decision mapping).
  - Added comprehensive unit test suite in `tests/test_prompt_programmatic_functions.py`.
- **Review Finding Feedback Dataset Export & Self-Improvement Loop**:
  - Exported verified finding dataset to `.data/feedback_dataset.jsonl` enabling downstream agentic self-improvement and prompt evaluation.
- **Universal Multi-Stage Workflow Orchestration Pipeline (`src/devops_cli/pipeline/`, `tests/test_pipeline_engine.py`)**:
  - Introduced generic `StagePipeline[ContextT, ResultT]` and `PipelineStage` framework supporting sequential and DAG-based stage execution with scratchpad context passing.
  - Granular `@trace_span` telemetry waterfalls, error isolation, and metrics collection (`pipeline_runs_total`, `pipeline_run_duration_seconds`).
- **Unified Async HTTP/2 Connection & Security Broker (`src/devops_cli/http/broker.py`, `tests/test_http_broker.py`)**:
  - Centralized thread-safe `HttpClientBroker` managing shared `httpx2` client connection pools with HTTP/2 multiplexing, SSRF private network isolation, and traceparent propagation.
- **Local Kubernetes Chaos & Fault Injection Runner (`src/devops_cli/k8s/chaos_runner.py`, `tests/test_k8s_chaos_runner.py`)**:
  - Added `ChaosFaultRunner` supporting declarative pod disruptions, recovery time observation, and automatic rollback handling.
- **Continuous IDE File Watcher & Instant Review (`devops ai review path --watch`)**:
  - Added `--watch` / `-w` and `--debounce-ms` options to `devops review path` leveraging `DebouncedFileWatcher` to trigger instant multi-persona reviews on active file changes.
- **Automated Kubernetes Stack Credential Synchronization (`src/devops_cli/k8s/credentials.py`, `devops k8s sync-secrets`)**:
  - Added zero-plaintext credential extraction from Kubernetes Secrets (`argocd-initial-admin-secret`, `kube-prometheus-stack-grafana`, `grafana`) directly into OS Keyring (`argocd_password`, `grafana_password`).
  - Integrated automated credential synchronization into `devops k8s deploy-stack` and `devops k8s sync-secrets`.
- **Automated Dependency Vulnerability Remediation PR Engine (`src/devops_cli/security/dependency_remediator.py`, `devops scan fix`)**:
  - Added `DependencyRemediator` automating CVE patching across lockfiles (`uv lock --upgrade-package`), dry-run remediation planning, and git topic branch staging (`fix/security-<cve>`).
  - Registered `scan_fix` FastMCP tool for autonomous agent-driven dependency remediation.
- **Isolated Dockerized Workload Sandbox Environment (`src/devops_cli/docker/sandbox.py`, `devops test sandbox`, `devops docker sandbox`)**:
  - Added `WorkloadSandboxRunner` providing rootless, ephemeral container test harnesses with bound workspace directories, resource quotas (`--memory`, `--cpus`), network isolation (`--network none`), and automatic container teardown.
  - Registered `docker_sandbox` FastMCP tool.
- **Enterprise HashiCorp Vault & Cloud KMS Secret Broker (`src/devops_cli/security/vault_broker.py`, `devops vault`)**:
  - Added `VaultSecretBroker` supporting Vault KV-v2 REST engine, URI references (`vault://<path>#<key>`), zero-plaintext storage, and seamless fallback to OS Keyring.
  - Added `devops vault` subcommands (`status`, `get`, `set`, `sync`) and registered `vault_status` and `vault_get` FastMCP tools.
- **Kubernetes Background Port-Forward Daemon Management (`src/devops_cli/k8s/port_forward_daemon.py`, `devops k8s port-forward`)**:
  - Added `PortForwardDaemonManager` with managed PID lifecycle tracking (`.data/k8s/port_forwards.json`), status inspection (`devops k8s port-forward-status`), and graceful process termination (`devops k8s port-forward-stop`).

### Changed
- **Removal of Heuristic Invalidation and Validation Functions**:
  - Removed heuristic auto-invalidation functions (`_check_contextual_exemption`, `_check_kustomization_namespace_exemption`, `_check_iac_operational_outputs`, `_check_missing_symbol_hallucination`, `_check_syntax_error_hallucination`, `_check_line_boundaries`) from `src/devops_cli/ai/review/verification.py` to prevent suppressing valid security defects.
  - Fixed verification default to `verified=False` preventing unverified findings from falsely validating.
  - Removed synthetic criteria count ratio scoring in finding verification.
  - Refined adversarial debate invalidation to preserve valid findings mentioning dependencies like `httpx2`.
  - Removed blanket exclusion instructions from `guardrails_isolation.md` and `verify_finding_system.md`.
- **Legacy & Shim Code Elimination**:
  - Removed legacy sequential single-prompt embedding fallback (`_fetch_fallback_single_embeddings`) in `src/devops_cli/ai/rag/embeddings.py`.
  - Cleaned up obsolete v0.1.1 feature comments and stubs in `src/devops_cli/commands/config.py`, `src/devops_cli/config/settings.py`, and `src/devops_cli/config/options.py`.
  - Updated review CLI docstrings to eliminate vestigial version tags.

### Security
- **Defense-in-Depth Path Traversal & SSRF Hardening**:
  - Enforced `allow_traversal=False` default in `validate_path` (`src/devops_cli/core/validation.py`).
  - Added DNS rebinding resolution to `_is_private_or_loopback` in `src/devops_cli/ai/common_tools.py`.
  - Added secret and credential token redaction (`***REDACTED***`) across agent hooks in `src/devops_cli/ai/agents/persistence.py`.
  - Added directory traversal guards to SQLite step store and symlink boundary containment guards across `aibom.py`, `kubeconform.py`, `skills.py`, and `pre_analysis.py`.
  - Sanitized prompt template variables in `ManagedPrompt.render` (`src/devops_cli/ai/agents/prompt.py`).


## [0.2.8] - 2026-09-01

### Added
- **Modular Output Formatters Subpackage (`src/devops_cli/output/formatters/`, `tests/test_fast_dispatch.py`)**:
  - Deconstructed monolithic formatting engine into modular, single-responsibility submodules: `scalars.py`, `tables.py`, and `panels.py`.
  - Added dedicated polymorphic TablePayload builders and finding panel formatters exposed via `devops_cli.output`.
- **Centralized Language Messages & Badges (`src/devops_cli/lang/en/messages.py`)**:
  - Added `BadgeMessages` and `OutputMessages` dataclasses to `LanguageCatalog` for full localization of terminal badges, status indicators, and headers.
  - Localized Kubernetes node status strings (`node_ready`, `node_not_ready`) and table titles.

### Changed
- **Declarative Dispatch Tables & Cyclomatic Complexity Elimination**:
  - Refactored AST symbol streaming in `src/devops_cli/ai/ast_stream.py` to use table-driven `_NODE_HANDLERS` dictionary and recursive decorator extraction.
  - Implemented declarative `_NATIVE_TOOL_SETTINGS_BUILDERS` and `_extract_local_tools` in `src/devops_cli/ai/agents/capabilities.py`.
  - Decoupled sub-agent execution in `src/devops_cli/ai/harness/workflow.py` via `_invoke_agent_callable`.
  - Replaced procedural truncation in `src/devops_cli/ai/harness/compaction.py` with `_TRUNCATION_FORMATTERS` and `_apply_compactor`.
  - Simplified settings coercion in `src/devops_cli/config/settings.py` via `_coerce_setting_value`.
  - Extracted certificate reading in `src/devops_cli/crypto/tls_certificates.py` via `_read_cert_bytes`.
- **Documentation Alignment & DevContainer Standardization (`docs/`)**:
  - Pinned container tag examples in `docs/DEVCONTAINER_USAGE.md` to current release (`v0.2.8`).
  - Aligned `docs/PENDING_FEATURES.md` and `docs/ROADMAP.md` reflecting completed v0.2.8 milestones.

### Removed
- **Zombie Code & Legacy Shims**:
  - Removed obsolete shims: `src/devops_cli/ai/review/rendering.py`, `src/devops_cli/models/dry_run.py`, and `src/devops_cli/core/dry_run.py`.
  - Merged `SSHKeyInfo` into `src/devops_cli/models/ssh.py` and deleted redundant `src/devops_cli/models/github.py`.
  - Cleaned duplicate entries in `src/devops_cli/output/__init__.py::__all__`.

## [0.2.7] - 2026-09-01

### Added
- **AI Bill of Materials (AIBOM) Generator & Model Curation (`src/devops_cli/security/aibom.py`, `src/devops_cli/commands/scan.py`, `tests/test_aibom.py`)**:
  - CycloneDX 1.5-compliant AI Bill of Materials (`devops scan aibom`) extracting model architecture parameters, licensing models (Permissive, Open-Source, Capped, RAIL, Proprietary), safe tensor formats, and cryptographic SHA-256 weight hashes.
  - Automated `trust_remote_code` AST and config analyzer detecting risky remote execution scripts before GPU provisioning.
  - Serving hardware heuristic estimator calculating peak RAM, inference VRAM, and disk storage for dense and Mixture-of-Experts (MoE) models across quantization bit-depths.
- **Zero-Allocation AST Symbol & Token Stream Parser (`src/devops_cli/ai/ast_stream.py`, `tests/test_ast_stream.py`)**:
  - Generator-based streaming parser yielding structural classes, functions, decorators, and imports without allocating intermediate node trees.
  - Line-level token streaming identifying indentation depths, comments, and string literals.
- **Cross-Encoder Context Re-Ranker & Deep Semantic RAG (`src/devops_cli/ai/rag/reranker.py`, `tests/test_rag_reranker.py`)**:
  - `CrossEncoderReranker` evaluating full query-chunk cross-token interaction density and reciprocal positional weighting.
- **"Big Decides, Small Types, Big Checks" Multi-Agent Synthesis Protocol (`src/devops_cli/ai/agents/synthesis_protocol.py`, `tests/test_synthesis_protocol.py`)**:
  - Three-stage synthesis pipeline orchestrating frontier planning models (Big Decides), fast local drafting models (Small Types), and frontier auditor models (Big Checks).
- **High-Performance Streaming Serializers (`src/devops_cli/output/streaming_serializer.py`, `tests/test_streaming_serializer.py`)**:
  - Low-memory streaming serializers for JSON arrays (`stream_json_array`), line-delimited JSON (`stream_jsonl`), and multi-document YAML (`stream_yaml_docs`).

### Fixed
- **SSH Key Prefix Configuration & Options Across Subcommands (`src/devops_cli/commands/ssh.py`, `src/devops_cli/crypto/ssh_keys.py`, `tests/test_ssh.py`)**:
  - Enhanced `devops ssh register` with `--prefix` / `-p` option and ensured it honors configured `settings.ssh.key_prefix` when discovering keys and generating registration titles.
  - Added prefix filtering and fallback in `find_newest_key()`, `list_managed_keys()`, and `list_managed_keys_info()`.
  - Added `--prefix` / `-p` support to `devops ssh status` and `devops ssh list` / `devops ssh audit`.
  - Exported `parse_key_prefix` and `list_managed_keys_info` in `devops_cli.crypto`.

## [0.2.6] - 2026-08-31

### Added
- **Multi-Dimensional AI Model Routing & Governance (`src/devops_cli/ai/router.py`, `tests/test_ai_router.py`)**:
  - Dynamic multi-axis model routing across task complexity (`LOW`, `MEDIUM`, `HIGH`, `FRONTIER`), task freshness (`STATIC_CONTEXT`, `LIVE_MCP_LOOKUP`, `EXTERNAL_WEB_SEARCH`), and data sensitivity (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL_AIRGAP`).
  - Air-gap data egress enforcement redirecting confidential workloads to local air-gapped models (`ollama`) with local fallback chains.
  - Cost and latency tier forecasting (`sub-second`, `fast-interactive`, `multi-second`, `deep-reasoning`) for AI execution plans.
  - Knowledge Base topic manual for Model Governance, Routing & Curation (`src/devops_cli/ai/knowledge_base/it_domains/topics/model_governance_routing_and_curation.md`).
- **AST Code Complexity & SBOM Generation (`src/devops_cli/security/complexity.py`, `src/devops_cli/security/sbom.py`, `src/devops_cli/commands/scan.py`)**:
  - AST cyclomatic complexity analyzer (`devops scan complexity`) computing per-function and per-module complexity scores and identifying nested branching.
  - Software Bill of Materials generator (`devops scan sbom`) supporting CycloneDX and SPDX formats from active lockfiles and installed packages.
- **Git-Diff Aware Targeted Test Execution (`src/devops_cli/commands/test_cmd.py`, `tests/test_test_runner.py`)**:
  - Added `devops test run --diff` discovering and executing only test files affected by unstaged or branch-level git diffs.
- **Live Resource & State Watchers Across Subsystems (`src/devops_cli/watchers/live_resource.py`, `src/devops_cli/commands/`)**:
  - Added `--watch` / `-w` and `--interval` support powered by `rich.live.Live` across `devops k8s pods --watch`, `devops docker stats --watch`, `devops argo cd apps list --watch`, and `devops release status --watch`.
  - Added `devops docker stats` command with real-time CPU%, memory net usage/limit, and network RX/TX I/O statistics table.
  - Added `devops k8s pods` command with real-time pod phase, ready container counts, restart metrics, and age reporting.
- **In-Memory SHA-256 Embedding LRU Cache (`src/devops_cli/ai/rag/embeddings.py`, `tests/test_rag_embeddings.py`)**:
  - Implemented thread-safe in-memory LRU cache (`_EmbeddingLRUCache`) keyed by SHA-256 hash of text and model identifier, accelerating repeated RAG queries and semantic search.
  - Instrumented embedding cache hits, misses, and active size metrics via OpenTelemetry/Prometheus.

### Changed
- **AST Chunking, Tool Registries & Review Stage Cyclomatic Complexity Reduction (`src/devops_cli/ai/rag/chunker.py`, `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/ai/review/stages/`)**:
  - Decomposed complex multi-branch functions in AST chunking, tool registries, and review stages into dedicated single-responsibility helper functions and functional pipelines.
- **DevContainer Standalone Binary Isolation & Mount Hardening (`.devcontainer/devcontainer.json`, `src/devops_cli/commands/devcontainer.py`)**:
  - Configured dynamic interpreter path (`${containerWorkspaceFolder}/.venv/bin/python`) and remote environment `PATH`.
  - Preserved native `/usr/local/bin/devops` installation without overwriting with broken workspace symlinks.
  - Standardized cross-platform SSH mount syntax (`${localEnv:HOME}${localEnv:USERPROFILE}/.ssh`).

## [0.2.5] - 2026-08-27

### Added
- **Zero-Plaintext Invariant & Keyring Egress Security Audit (`tests/test_zero_plaintext_invariants.py`, `devops_cli.exceptions.security`)**:
  - Automated continuous regression suite verifying zero unencrypted secrets, tokens, or private keys exist across configuration files, `.data/`, `.devops/`, test fixtures, or docs.
  - Added `InsecureConfigError` with canonical exit code `126` (`E_INSECURE_CONFIG`) and contextual path masking.
- **FastMCP Tool Schema Completeness & Strict Type Validation (`tests/test_fastmcp_contracts.py`, `devops_cli.ai.mcp.server`)**:
  - Registered 6 new FastMCP tools (`ai_repomap`, `ai_diagram`, `ai_test_gen`, `config_audit_keys`, `telemetry_profile`, `tf_notify_plan`), bringing total registered tools to 40.
  - Verified 100% parameter descriptions, strict type annotations, structured JSON schemas, and flag injection defenses across all tools.
- **Universal Pydantic Resource Model Catalog (`devops_cli.models`)**:
  - Standardized request and result resource models across all domain subsystems (`docker`, `k8s`, `security`, `tf`, `config`, `workspace`, `release`, `ci`, `git`, `ai`) with dynamic FastMCP resource endpoints (`resource://*`).
- **DevContainer Workspace Cache Volumes & Lifecycle Management (`devops_cli.commands.devcontainer`, `.devcontainer/devcontainer.json`)**:
  - Configured dedicated Docker named volume mounts for `.uv`, `.venv`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, and `.data` for native Linux `ext4` I/O throughput on Windows hosts.
  - Added automated `post-create` and `post-start` permission enforcement ensuring standard cache directories are created and chowned to the active container user (`vscode`).
- **Team IDE Configuration & MCP Tracking (`.gitignore`, `.vscode/mcp.json`)**:
  - Permitted version-controlled tracking of shared `.vscode/` team configurations (`mcp.json`, `settings.json`, `tasks.json`, `launch.json`) in `.gitignore` while continuing to ignore user-specific overrides.
- **Structural Diff Path Containment & Arbitrary File Read Hardening (`devops_cli.ai.diff.difftastic`, `tests/test_difftastic.py`)**:
  - Enforced strict repository boundary validation with `resolve_safe_subpath` in `get_structural_diff`, mitigating arbitrary file read and information exposure risks (CWE-200 / CWE-284).

### Changed
- **Target Path Resolution & Pre-Analysis Metadata Refinement (`devops_cli.commands.review`, `devops_cli.ai.review.pipeline`)**:
  - Enforced absolute target path resolution across review commands and stage trace spans, eliminating relative `.` path ambiguity and path segment duplication in finding locations.
- **AST Structural Standardization & Strict Indentation Budgeting**:
  - Audited project-wide control flow and refactored all functions exceeding indentation depth limits, achieving **0** functions with depth $\ge 6$ across the entire repository.
  - Refactored `_render_review_result` in `rendering.py`, `_analyze_python_ast` in `scanner.py`, `_find_plaintext_config_leaks` in `config.py`, `chunk_file` in `chunker.py`, `Finding._pre_validate_finding` in `review_schema.py`, `_from_otlp_any_value` in `tracer.py`, and `render_table` in `formatter.py` into dedicated functional pipelines and standard library helpers.
- **Cold Import Latency Optimization & Lazy Loader Consolidation**:
  - Verified CLI cold import isolation, keeping `devops_cli.main` load overhead sub-second and deferring heavy third-party packages (`kubernetes`, `fastmcp`, `boto3`, `trivy`, `pydantic_ai`) to command execution time.
- **Workspace Data Tier Standardization (`.data/scratch/`)**:
  - Consolidated temporary and exploratory scripts into `.data/scratch/` ensuring 100% data artifacts reside within the centralized `.data/` tier.

## [0.2.4] - 2026-08-27

### Added
- **Trace Waterfall Visualizer CLI (`devops telemetry profile`, `devops_cli.telemetry.tracer`)**:
  - Implemented interactive terminal waterfall breakdown and latency heatmap of OpenTelemetry spans.
  - Added subcommands for span filtering by trace ID, last recorded trace, and direct command execution profiling.
- **Keyring Token Housekeeping & Secret Health Auditor (`devops config audit-keys`, `devops_cli.commands.config`)**:
  - Implemented OS Keyring backend health auditing, token state verification, and zero-plaintext file scanning.
- **FastMCP Tool Schema Contract Regression Suite (`tests/test_fastmcp_contracts.py`)**:
  - Added regression test suite verifying tool registration, parameter descriptions, typed signatures, and flag injection defenses across all 35+ FastMCP tools.
- **Aider-Style AST Repository Map Generator (`devops ai repomap`, `devops_cli.ai.repomap`)**:
  - Compact whole-repo symbol and relationship map generator parsing AST signatures and docstrings without context window overflow.
- **Architecture & Threat Modeling Diagram Synthesis (`devops ai diagram`, `devops_cli.ai.diagram`)**:
  - Automated Mermaid architecture topology (`graph TD`) and STRIDE zero-trust threat flowcharts (`graph LR`).
- **Prompt Mutation Testing & Benchmark Guardrails (`devops ai prompt-eval`, `devops_cli.ai.prompt_eval`)**:
  - Mutation benchmark suite evaluating persona prompt variations against ground truth feedback datasets. *(Correction: shipped as a deterministic suppression benchmark under that label without prompt perturbation; see #385 and #600).*
- **Automated Unit Test Synthesizer (`devops ai test-gen`, `devops_cli.ai.test_gen`)**:
  - Synthesizes isolated pytest test suites from AST signatures and uncommitted diffs.
- **Automated PR Remediation Branch Generator (`devops ai review auto-fix`, `devops_cli.ai.review.auto_fix`)**:
  - Generates corrective topic branches (`fix/finding-<id>`) with staged patches and unit test verifications.
- **tfcmt Automated PR Plan Notifier (`devops tf notify-plan`, `devops_cli.commands.tf`)**:
  - Formats structured, collapsible OpenTofu/Terraform plan diff summaries for automated PR comments.
- **Streaming SSE / WebSocket Agent Reasoning Feed (`devops serve /stream` & `/ws`, `devops_cli.server.routes.stream`)**:
  - Server-Sent Events (SSE) and duplex WebSocket feeds streaming real-time LLM token generation and reasoning scratchpad updates.
- **Hybrid Dense-Sparse RAG Tier (BM25 + Qdrant RRF, `devops_cli.ai.rag.retriever`)**:
  - Reciprocal Rank Fusion (RRF) combining dense embeddings with sparse keyword search scores.
- **Async HTTP/2 Connection Pooling & Client Reuse (`devops_cli.http.client`)**:
  - Added `new_async_http_client` with HTTP/2 support and connection pooling.

## [0.2.3] - 2026-08-26

### Added
- **Centralized Parameter Defaults & Invariant Constants Architecture (`devops_cli.config.defaults`, `devops_cli.config.constants`)**:
  - Centralized all inline parameter default values across functions and CLI subcommands into `src/devops_cli/config/defaults.py` and `src/devops_cli/config/constants.py`.
  - Added declarative subprocess argument builders in `src/devops_cli/config/commands.py` (`build_kubectl_cmd`, `build_kustomize_build_cmd`, `build_bandit_cmd`, `build_trivy_scan_cmd`, `build_popeye_cmd`, `build_kubelinter_cmd`, `build_pluto_cmd`, `build_uv_audit_cmd`, `build_tf_cmd`, `build_tofu_cmd`, `build_gitleaks_cmd`, `build_semgrep_cmd`).
- **Declarative Output Renderable Models (`devops_cli.output.models`)**:
  - Implemented declarative Pydantic v2 schemas (`TablePayload`, `PanelPayload`, `MarkdownPayload`, `SyntaxPayload`, `RulePayload`, `KeyValuePayload`, `MessageLevel`) with encapsulated Rich console rendering in `devops_cli.output`.
- **Comprehensive Domain Exception Taxonomy (`devops_cli.exceptions`)**:
  - Standardized strongly typed exceptions under `src/devops_cli/exceptions/` (`DevOpsCLIError`, `GitOperationError`, `InvalidBranchNameError`, `InvalidURLError`, `SecurityValidationError`, `ToolExecutionError`, `AIProviderError`, `ConfigurationError`).
  - Configured explicit POSIX exit codes, canonical machine-readable error codes, and structured error contexts project-wide.
- **Fast Typer Startup & PEP 562 Lazy Loading**:
  - Optimized CLI command dispatch with Typer lazy loading and stateless PEP 562 `__getattr__` / `_get` resolution across subcommands (`repos`, `branches`, `ci`, `mcp`, `release`, `uv`, `workspace`).

## [0.2.2] - 2026-08-25

### Added
- **Checkov IaC Static Policy & Compliance Engine (`devops scan iac`, `devops scan checkov`, `devops_cli.security.checkov`)**:
  - Implemented static compliance and policy security auditing across Terraform, CloudFormation, Kubernetes, and Dockerfile manifests.
  - Added CLI subcommands `devops scan iac <target>` and `devops scan checkov <target>` with Rich table and JSON exports.
  - Registered `scan_iac` native persona tool and bundled Knowledge Base manual: `it_domains/tools/checkov.md`.
- **TFLint Cloud Provider Linter (`devops tf lint`, `devops_cli.security.tflint`)**:
  - Implemented deep static Terraform/OpenTofu validation against cloud provider rules, deprecated syntax, and module variable constraints.
  - Added CLI subcommand `devops tf lint <dir> [--config FILE] [--json]`.
  - Registered `tf_lint` native persona tool and bundled Knowledge Base manual: `it_domains/tools/tflint.md`.
- **Dive Docker Layer Efficiency Analyzer (`devops docker analyze-layers`, `devops_cli.security.dive`)**:
  - Container image layer exploration and wasted space analysis computing efficiency scores and layer breakdowns.
  - Added CLI subcommand `devops docker analyze-layers <image> [--json]`.
  - Registered `docker_analyze_layers` native persona tool and bundled Knowledge Base manual: `it_domains/tools/dive.md`.
- **Kubeconform Fast OpenAPI Schema Validator (`devops k8s validate`, `devops_cli.security.kubeconform`)**:
  - Fast offline Kubernetes manifest validation against OpenAPI JSON schemas supporting arbitrary target Kubernetes versions and strict validation.
  - Added CLI subcommand `devops k8s validate <target> [--kubernetes-version STR] [--strict] [--json]`.
  - Registered `k8s_validate_manifests` native persona tool and bundled Knowledge Base manual: `it_domains/tools/kubeconform.md`.
- **Dynamic Cost- & Latency-Aware LLM Router (`devops ai route`, `devops_cli.ai.router`)**:
  - Task complexity classification and intelligent query steering between local Ollama models and frontier cloud models with estimated cost tracking.
  - Added CLI subcommand `devops ai route <task> [--tokens INT] [--frontier] [--json]`.
- **Automated Workspace & Data Tier Housekeeping Engine (`devops workspace clean`, `devops_cli.core.cleanup`)**:
  - Added retention policy pruning for stale review runs, temporary analysis caches, and trace logs under `.data/`.
  - Added CLI subcommand `devops workspace clean [--older-than INT] [--dry-run]` with top-level alias `devops clean`.

## [0.2.1] - 2026-08-25

### Added
- **Local Context Budgeting & Token Counting Engine (`devops ai token-count`, `devops_cli.ai.context_budget`)**:
  - Implemented Byte-Pair Encoding (BPE) token counting using `tiktoken` with model-family encoding resolution (`o-series`, `gpt-4o`, and character-ratio fallback).
  - Added semantic prefix-preserving truncation (`truncate_to_token_limit`) and hunk-aware git diff budgeting (`budget_diff_chunks`) to prevent context window overflow (HTTP 400).
  - Added CLI command `devops ai token-count <target> [--budget INT] [--model STR] [--json]` with Rich breakdown tables.
  - Bundled Knowledge Base tool manual: `it_domains/tools/tiktoken.md`.
- **Gitleaks Sub-Millisecond Secret Pre-Filter (`devops scan secrets`, `devops scan gitleaks`, `devops_cli.security.gitleaks`)**:
  - Subprocess runner with native regex fallback pattern scanning AWS access keys, GitHub PATs, OpenAI API keys, RSA/EC private key blocks, and Stripe tokens.
  - Integrated into Stage 2 code review pipeline (`devops_cli.ai.review.pipeline`) to scrub uncommitted secrets before LLM prompt dispatch.
  - Added CLI subcommands `devops scan secrets <target>` and `devops scan gitleaks <target>` with Rich table and JSON exports.
  - Registered `scan_gitleaks` native persona tool and bundled Knowledge Base manual: `it_domains/tools/gitleaks.md`.
- **Semgrep Static AST Pattern Matcher (`devops scan semgrep`, `devops scan sast`, `devops_cli.security.semgrep`)**:
  - Polyglot static AST pattern matching runner (`p/default`) with structured finding normalization (`Finding` models).
  - Integrated into Stage 2 code review pipeline for multi-language AST vulnerability scanning.
  - Added CLI subcommands `devops scan semgrep <target>` and `devops scan sast <target>`.
  - Registered `scan_semgrep` native persona tool and bundled Knowledge Base manual: `it_domains/tools/semgrep.md`.
- **PydanticAI Standardized Agent Framework (`devops_cli.ai.pydantic_ai_bridge`)**:
  - Standardized PydanticAI Agent bridge adapter (`create_pydantic_ai_agent`, `get_persona_pydantic_agent`) supporting strongly typed output models, dynamic parameter inspection, and persona workflows (`devsecops`, `architect`, `qa`, `pm`).
  - Bundled Knowledge Base manual: `it_domains/tools/pydantic_ai.md`.
- **Modular AI Review Pipeline Stages (`devops_cli.ai.review.stages`)**:
  - Decomposed the multi-stage review orchestrator into dedicated single-responsibility stage modules (`pre_analysis.py`, `static_scan.py`, `persona_review.py`, `verification.py`, `reranking.py`, `reporting.py`) with `@trace_span` telemetry instrumentation.
- **LLM Provider Abstraction Layer (`devops_cli.ai.providers`)**:
  - Modular provider protocol architecture (`BaseLLMProvider`) with dedicated provider implementations for `ollama`, `openai`, `claude`, `copilot`, and `mock` for deterministic test isolation.
- **Standardized Domain Exception Taxonomy (`devops_cli.exceptions`)**:
  - Strongly typed exception hierarchy (`DevOpsCLIError`, `SecurityError`, `SSRFBlockedError`, `KeyringUnavailableError`, `SecretExposureError`, `LLMInferenceError`, `ContextBudgetExceededError`, `ModelUnavailableError`, `PersonaExecutionError`) with explicit POSIX exit codes and canonical error codes.
- **In-Memory Prometheus Metrics Collector & Context Propagation (`devops_cli.telemetry.metrics`, `devops_cli.telemetry.context`)**:
  - Thread-safe in-memory metric registry (`GLOBAL_METRICS`, `InMemoryMetricsRegistry`) tracking counters, gauges, and histograms with Prometheus text exposition format and W3C traceparent header propagation (`inject_traceparent_headers`, `extract_traceparent`).
- **Strategic Roadmap Grooming & Industry Tool Integrations (`docs/ROADMAP.md`)**:
  - Extended and groomed the strategic roadmap through v0.3.0 incorporating advanced AI research (Multi-Agent Adversarial Debate, Spec-Driven Development, Dynamic Cost/Latency Router, Automated Test Synthesizer, Hybrid BM25+Qdrant Search, Cross-Encoder Re-Ranking) and open-source DevOps tooling (TFLint, Dive, Kubeconform, Stern, Helm-diff, Difftastic, tfcmt, Falco).

### Fixed
- **CodeQL Security Hardening**:
  - Resolved `py/stack-trace-exposure` on `/api/v1/telemetry` by sanitizing OTLP probe error returns and logging internal exception details via `logger.debug`.
  - Resolved `py/clear-text-storage-sensitive-data` in `file_writer.py` by allocating file descriptors using `os.open` with restrictive POSIX file creation modes (`0o644` / `0o600`) and upfront `os.chmod` on atomic temporary files.

## [0.2.0] - 2026-08-25

### Added
- **Published DevContainer Image Scaffolding Engine (`devops devcontainer init`, `devops_cli.commands.devcontainer`)**:
  - `devops devcontainer init` now defaults to the pre-built, published container image `ghcr.io/dan-petty/devops-cli/devcontainer:latest`.
  - Streamlined `devcontainer.json` generation omitting redundant feature blocks when using the published image, eliminating unnecessary tool builds in child repositories.
  - Added `--home-volume` option to configure custom persistent `/home/vscode` named volumes.
  - Added `--force` (`-f`) flag for in-place re-scaffolding of `.devcontainer/` and `.vscode/mcp.json`.
- **Pre-baked DevContainer Dockerfile & uv Integration**:
  - Created `.devcontainer/Dockerfile` pre-baking standalone `uv` and `uvx` binaries from `ghcr.io/astral-sh/uv:latest` and installing `devops-cli` globally.
  - Added self-bootstrapping lifecycle hooks in `postCreateCommand` for seamless container startup across all target repositories.
- **Pull Request DevContainer Image Publishing (`.github/workflows/ci.yml`)**:
  - Added automated GitHub Container Registry (GHCR) image builds for Pull Requests tagged with `pr-<number>` (without the `latest` tag) to enable pre-merge devcontainer validation.
- **Fault-Tolerant Code Review Pipeline (`devops_cli.ai.review.pipeline`)**:
  - Graceful per-file error isolation across all 6 review pipeline stages (pre-analysis, payload initialization, multi-persona review, verification, re-ranking, and report generation).
  - Skips failing files without crashing multi-file reviews and outputs dedicated Rich console tables and a Markdown `## Skipped / Errored Files` section in `review.md`.
- **Comprehensive Distributed Tracing & Subcommand Hierarchy (`devops_cli.telemetry`)**:
  - Unified command proxy delegation in `main.py` nesting all child commands, subprocess executions, and multi-agent pipeline stages under the root `cli.<subcommand>` span.
  - Instrumented OpenTelemetry spans across workspace RAG indexing (`ai.rag.index_workspace`, `ai.rag.upsert_chunk_batch`, `ai.rag.embed_texts`, `ai.rag.ollama_embed_batch`, `qdrant.upsert_points`).
  - Added `BaseException` handling in `trace_span` to capture `KeyboardInterrupt` and `SIGINT` cancellations with error tags and status attributes.

### Changed
- **Zero Hardcoded Scoring Policy & Agent Instruction Standards**:
  - Eliminated synthetic confidence floats, fallback weights, and static scoring defaults project-wide.
  - All review findings and quality ratings originate strictly from native external security scanners (Bandit, Trivy, OSV, Pluto) or structured LLM responses.
- **RAG Collection Isolation**:
  - Separated workspace indexing and knowledge base indexing into distinct Qdrant collections (`devops_code`, `devops_docs` vs `kb_code`, `kb_docs`) to prevent point deletion collisions.
- **Performance Optimizations & In-Memory Caching**:
  - Optimized repository file discovery in `runner.py` by eliminating redundant `git check-ignore` subprocesses for files already sourced from `git ls-files --exclude-standard`.
  - Cached compiled `.gitignore` pattern matching using `@functools.lru_cache` on `pathspec.PathSpec`.
  - Added RAG investigation memoization (`_INVESTIGATION_CACHE`) with a 60-second TTL and client reuse.
  - Cached `QdrantClient.is_alive()` status (15-second TTL) to eliminate repetitive HTTP collection probes.
  - Added robust integer coercion for `offset` and `max_bytes` in the `read_file` agent tool.
- **Default Git Configuration**:
  - Automatically configured default branch `main` and `push.autoSetupRemote true` across DevContainer post-start lifecycles.
- **Pure uv Toolchain Standardization**:
  - Replaced legacy pip invocations across all Dockerfile builds and devcontainer templates with pure `uv` commands (`uv tool install` and `uv pip install --system`).

## [0.1.13] - 2026-08-24

### Added
- **Embedding Model Benchmark Suite (`devops ai benchmark --type embedding`, `devops_cli.ai.benchmark`)**:
  - Dedicated vector embedding benchmark engine (`EmbeddingBenchmarkRunner`, `EmbeddingBenchmarkResult`, `EmbeddingBenchmarkReport`) evaluating dense vector embedding models (`qwen3-embedding`, `nomic-embed-text`, `all-minilm`, `bge-*`, `text-embedding-3-*`).
  - Automatic model classification and CLI routing in `devops ai benchmark` when embedding models are provided.
  - Evaluation corpus of 15 domain-specific query-passage pairs across 5 DevOps domains (Security, Kubernetes, Architecture, CI/CD, Infrastructure) and 10 distractor passages.
  - Evaluates semantic retrieval quality (Recall@1, Recall@3, Mean Reciprocal Rank (MRR), and Cosine Margin), single-query latency (p50/p95 ms), batch throughput (items/sec and chars/sec), and vector health ($L_2$ norm and dimension verification).
  - Rich interactive terminal leaderboard tables, JSON export to `.data/benchmarks/`, and Markdown summary rendering.
- **Local & Homelab TLS Certificate Management (`devops tls`, `devops cert`, `devops_cli.crypto`)**:
  - X.509 Certificate Authority and TLS server/client certificate generation using `cryptography.x509`.
  - Subject Alternative Name (SAN) auto-generation supporting IP addresses, hostnames, localhost, homelab `.lan` / `.local` domains, and Kubernetes service FQDNs.
  - Automated Kubernetes TLS secret provisioning (`devops tls inject-k8s-secret`, `devops k8s enable-tls`) and cert-manager ClusterIssuer integration for homelab/k3s/minikube environments.
- **Universal OpenTelemetry Integration (`devops telemetry`, `devops otel`, `devops_cli.telemetry`)**:
  - End-to-end telemetry configuration, status inspection, and OTLP trace export across all CLI operations and AI multi-agent pipelines.
  - Jaeger Query UI and OTLP collector deployment configurations in `k8s/otel/jaeger.yaml`.

- **OpenTelemetry Universal Command Tracing & Span Instrumentation (`devops_cli.telemetry.tracer`)**:
  - Full end-to-end command tracing spanning CLI subcommands (`branches`, `devcontainer`, `docker`, `github`, `install_tools`, `k8s`, `kustomize`, `mcp`, `pr`, `release`, `scan`, `tf`, `tls`, `tofu`, `uv`, `workspace`).
  - Trace span lifecycle attributes, sanitized arguments, duration tracking, error status recording, and custom OTLP header authentication support.

### Changed
- **Review Schema & Finding Deduplication Hardening (`devops_cli.ai.review_schema`)**:
  - Eliminated fragile literal collections, ad-hoc string lists, and keyword regex heuristics in favor of clean structural schema validation and standard path parsing.
  - Robust set-based token similarity with universal token length filtering and configurable line-range overlap tolerance for duplicate finding consolidation.
  - Hardened location parser handling POSIX URIs, GitHub-style anchors (`#L10-L20`), line ranges (`:10-20`), and Windows path conventions.
- **Standard Library & PEP 508 Code Hygiene Refactoring (`devops_cli.security.reference_extractor`)**:
  - Eliminated ad-hoc keyword lists and custom regex string splitting in favor of standard libraries (`ast`, `tokenize`, `packaging.requirements.Requirement`, `tomllib`, `json`, `yaml`, `urllib.parse`, `ipaddress`, `mimetypes`, `tldextract`).
  - Implemented PEP 508 requirement parsing for PyPI dependencies, PEP 621 `pyproject.toml` dependencies, optional dependency groups, and PEP 735 dependency groups.
  - Implemented AST string literal and comment tokenization for Python source code to eliminate false-positive domain matches on function calls, attributes, and variables.
  - Implemented RFC 2606 reserved domain exclusions (`.example`, `.test`, `.invalid`, `.localhost`) and strict public IP routability checks via `ipaddress.ip_address.is_global`.
- **Review Pipeline Linked File Context Optimization (`devops_cli.ai.review.pipeline`)**:
  - Added universal standard library filtering (`_UNIVERSAL_MODULES`) to prevent connecting all repository files via universal imports like `typing` or `pathlib`.
  - Bounded linked dependency files context to the top 10 relevant modules.
- **AI Review Tasks & Finding Verification Prompt Hardening**:
  - Hardened `src/devops_cli/ai/tasks/review.md` and `verify_finding.md` to prevent false positive detections and enforce actionable verification criteria.


## [0.1.12] - 2026-08-20

### Added
- **Universal Retrieval-Augmented Generation (RAG) Architecture (`devops ai rag`, `devops_cli.ai.rag`)**:
  - Polyglot syntax-aware AST chunker for Python, Go, Rust, TypeScript, JavaScript, Java, C/C++, Terraform/HCL, SQL, and Kubernetes YAML manifests.
  - Hierarchical technical documentation chunker preserving Markdown, AsciiDoc, and RST heading depth with breadcrumb hierarchy tracking.
  - Multi-project workspace autodetection (`Cargo.toml`, `go.mod`, `package.json`, `pyproject.toml`) and faceted semantic filtering (`--project`, `--language`, `--category`).
  - Native Qdrant vector database integration and Ollama dense embeddings generation (`all-minilm`).
- **Official `qdrant-client` SDK Adoption & Modernization**:
  - Replaced manual HTTP REST JSON calls with the official `qdrant-client` Python SDK with connection pooling, typed models, batch upserts, and payload filtering.
- **Hierarchical Configuration Modernization (`pydantic-settings`)**:
  - Upgraded `Settings` to inherit from `pydantic_settings.BaseSettings` with `SettingsConfigDict` supporting automatic environment variable binding (`DEVOPS_CLI_*`), schema validation, and secret masking while preserving OS Keyring security.
- **Multi-Context & Remote Cluster Kubernetes Support (`devops k8s`)**:
  - Added dynamic cluster reachability verification (`_cluster_reachable`) supporting remote k3s, EKS, and GKE cluster contexts via `kubectl cluster-info`.
  - Added `--context` (`-c`) option support across `deploy-stack`, `teardown-stack`, `port-forward`, and `configure-urls`.
  - Added automated iterative pre-existing Helm resource adoption (`_adopt_helm_resource_if_conflict`).
- **Multi-GPU Native Ollama DaemonSet Deployment**:
  - Integrated `k8s/llm/ollama-daemonset.yaml` with multi-GPU access (`NVIDIA_VISIBLE_DEVICES: "all"`), `runtimeClassName: nvidia`, hostPort 11434, and shared NFS model cache.
- **Structural Metadata Extraction Engine (`src/devops_cli/ai/rag/metadata.py`)**:
  - Polyglot dependency and import parsing across 8+ programming languages.
  - Automated security sensitivity classification tagging code chunks into `crypto`, `network`, `auth`, `secrets`, `db`, `fs`, and `iam`.
  - Document frontmatter metadata parser extracting YAML/TOML metadata and heading hierarchy metrics.
- **Multi-Signal Search Re-Ranking Engine (`src/devops_cli/ai/rag/reranker.py`)**:
  - Hybrid scoring fusion engine combining dense vector cosine similarity (0.60), lexical token overlap (0.25), exact symbol match bonuses (+0.15), query intent classification (+0.10 for docs/code), and security alignment (+0.10).
  - Attached transparent `rerank_score` and individual `rank_factors` to every retrieved chunk.
- **Universal AI Subcommand RAG Integration**:
  - `devops ai chat`: Per-turn conversational semantic retrieval (`--rag/--no-rag`).
  - `devops ai pipeline`: Seeds multi-agent review and reasoning pipelines with relevant codebase context.
  - `devops ai agents`: Retrieves architectural context and CLI conventions when generating canonical agent instructions.
  - `devops ai analyze`: Injects related architectural context during metadata analysis and pseudocode extraction.
  - `devops ai review`: Injects re-ranked cross-file context with symbol and security tags into multi-persona code reviews.
- **End-to-End OpenTelemetry Tracing & Observability Stack**:
  - Integrated OpenTelemetry trace lifecycle spans across LLM dispatches, pipeline stages, and CLI operations (`devops_cli.telemetry`).
  - Jaeger Query UI and OTLP collector deployment manifests (`k8s/otel/jaeger.yaml`).
  - Customized Grafana dashboards for AI inference latency, token metrics, and Kubernetes cluster health (`k8s/monitoring/dashboards/`).
- **DevContainer Background Git Daemon**:
  - Native automated background Git daemon with `--export-all` across `k8s` and `repos` during container post-start lifecycle.
- **GitHub PR Governance & Remote CI Inspection (`devops pr`)**:
  - Pull request lifecycle management (`create`, `status`, `checks`, `view`, `diff`) with automated release branch base targeting and CI check monitoring.
- **AI Review Subsystem Modularization & Decoupling**:
  - Refactored monolithic `commands/review.py` into cohesive domain modules under `src/devops_cli/ai/review/` (`runner.py`, `chunker.py`, `patching.py`, `exporter.py`, `verification.py`, `pipeline.py`).
- **Atomic AI Tasks, Finding Verification/Invalidation Criteria & Reportability Scoring**:
  - Decomposed AI review tasks into discrete, single-responsibility micro-steps to prevent prompt degradation.
  - Added explicit `verification_criteria` and `invalidation_criteria` to `Finding` data models.
  - Implemented criterion-based verification, deterministic confidence scoring, and `reportable: bool` assessment in review pipelines.
- **External Dependency Vulnerability Scanning & Network Reputation Auditing (`devops_cli.security.intelligence`)**:
  - Automated dependency extraction across Python (`pyproject.toml`, `requirements.txt`), JavaScript/TypeScript (`package.json`), Rust (`Cargo.toml`), and Go (`go.mod`) with live OSV.dev and NVD (NIST) vulnerability CVE lookups.
  - Automated extraction of external network references (public IPs, FQDNs, URLs in docs and source code) with Shodan InternetDB port/vulnerability and Cloudflare Radar threat reputation auditing.
  - Added formatted dependency and network intelligence tables to Markdown review reports and structured findings JSON payloads.
- **Universal AI Agent Memory & Automatic Summarization Engine (`devops_cli.ai.agents.memory`)**:
  - Incorporated structured `AgentMemory` with `MemoryEntry` tracking across all `PydanticAgent` instances, `MultiAgentPipeline` execution stages, and `devops ai chat` sessions.
  - Implemented automatic size-triggered context summarization (`auto_summarize_if_needed`) when interaction histories exceed message count or character limits, preserving critical technical decisions while consolidating older context.
- **Universal AI/LLM Response Fixer & JSON Recovery (`devops_cli.ai.fixer`)**:
  - Integrated `json-repair` library for resilient recovery and structural parsing of corrupted, truncated, or markdown-wrapped JSON payloads across all LLM inference streams.
  - Implemented thought-scratchpad filtering and dedicated natural language synthesis turns to guarantee clean user-facing outputs without leaked reasoning scratchpads.
- **Native Dependency Audit Tool (`scan_uv_audit`, `audit_dependencies`)**:
  - Integrated `uvx pip-audit` tools in native CLI tool registry (`devops_cli.ai.tools.native`) and FastMCP server (`devops_cli.ai.mcp.server`) for auditing Python dependencies in `pyproject.toml`, `uv.lock`, and `requirements.txt`.
- **Parallel Multi-Node LLM Prewarming (`devops ai chat --prewarm`)**:
  - Added parallel model prewarming and VRAM memory pinning (`keep_alive: "1h"`) across all configured Ollama cluster nodes at chat startup.
- **Architectural Separation of Constants and Defaults (`devops_cli.config`)**:
  - Decoupled immutable system invariants (`CONST_*` in `config/constants.py`) from configurable optional parameter defaults (`DEFAULT_*` in `config/defaults.py`).
  - Removed all `DEFAULT` prefixes and substrings from `CONST_` symbol definitions across the entire codebase.

### Changed
- **AI Agent Tool Execution & Anti-Repetition Loop Guardrails**:
  - Enforced parameter validation against tool schemas to eliminate stop-word argument hallucination.
  - Added duplicate tool call detection and autonomous natural language report synthesis in `PydanticAgent`.
- **Review Prompt & Verification Rule Hardening**:
  - Refined `src/devops_cli/ai/tasks/review.md` and `src/devops_cli/ai/tasks/verify_finding.md` to prevent speculative vulnerability reports on hypothetical helper behavior and eliminate false-positive syntax error hallucinations on standard Python 3 tuple exception handlers (`except (Err1, Err2):`).
  - Streamlined feedback dataset exporter (`devops ai review export-feedback`) to export complete review findings into `.data/feedback.jsonl` for continuous improvement benchmarks.

### Security
- **Path Traversal & Injection Defenses**:
  - Added strict path traversal defenses in `load_custom_repo_persona` (`src/devops_cli/ai/personas/__init__.py`).
  - Added tool description sanitization in `PydanticAgent` prompt construction (`src/devops_cli/ai/agents/pydantic_agent.py`) to prevent indirect prompt injection.
  - Added semantic version regex validation in `devops install-tools` binary downloads.
  - Added label format validation in `devops release prepare` before GitHub CLI invocation.
  - Switched Valkey deployment in `k8s/llm/valkey.yaml` from NodePort to `ClusterIP` and removed `--protected-mode no`.

### Fixed
- **API Boundary & Pipeline Invariants**:
  - Removed internal helper functions `_run_mcp_cmd` and `_validate_mcp_arg` from public `__all__` in `src/devops_cli/ai/mcp/__init__.py`.
  - Added positive integer validation for `max_turns_per_agent` and hoisted imports in `MultiAgentPipeline` (`src/devops_cli/ai/agents/pipeline.py`).
  - Added bounds enforcement on `top_k` and `score_threshold` and query masking in telemetry traces (`src/devops_cli/ai/rag/retriever.py`).

## [0.1.11] - 2026-08-18

### Added
- **Git & GitHub Project Best Practice Guardrails (`AGENTS.md`, `CONTRIBUTING.md`, `docs/ROUTINE_TASKS.md`)**: Comprehensive AI agent and developer operational guardrails for branch hierarchy (zero direct commits to `main`, base branch targeting `release/vX.Y.Z`, fresh topic branches), commit hygiene (Conventional Commits, atomicity, pre-commit validation, zero leaked secrets), PR governance (no autonomous merging by agents, in-place topic branch updates, active CI monitoring, and issue linking), and targeted unit testing during iterative feature development before full final-stage test runs.
- **Published Dev Container User Guide & CLI Scaffolding (`docs/DEVCONTAINER_USAGE.md`)**: Comprehensive user guide for consuming the published multi-tool GHCR DevContainer image (`ghcr.io/dan-petty/devops-cli/devcontainer:latest`) across VS Code, Cursor, and GitHub Codespaces, along with `--published` (`-p`) and `--image` (`-i`) flag support in `devops devcontainer init`.
- **Automated DevContainer Pre-Commit Installation**: Integrated automated `uv run pre-commit install` into the container startup lifecycle hook (`devops devcontainer run-lifecycle --post-start`) and added `.gitattributes` to enforce consistent LF line endings.

### Changed
- **Single Source of Truth Project Metadata Architecture**: Centralized metadata loading in `src/devops_cli/config/metadata.py` dynamically reading package version, description, and Python requirements directly from `pyproject.toml` and standard package distribution metadata (`importlib.metadata`), eliminating hardcoded version and configuration duplication across commands and defaults.
- **AI / LLM Prompt & Token Density Optimization**: Optimized persona domain prompts (`devsecops`, `architect`, `auditor`, `pm`, `qa`) and core review task prompts (`review.md`, `analyze_pseudocode.md`, `verify_finding.md`, `compose.md`, `metadata.md`, `chat.md`), eliminating cross-prompt rule duplication and reducing prompt token consumption.
- **CI Workflow Optimization & Duplicate PR Check Elimination**: Refactored `.github/workflows/ci.yml` to restrict `push` triggers strictly to `main` while maintaining `pull_request` triggers on `main` and `release/**`, eliminating duplicate CI runs on pull requests, and added workflow concurrency management to cancel superseded in-flight builds.
- **Evergreen Validation Nomenclature**: Standardized validation terminology across GitHub Actions workflows, CLI tooling, and documentation from numbered gates to evergreen `validate` / `Validation`.

### Fixed
- **DevContainer MCP & Minikube Initialization Resilience**: Enhanced `devops devcontainer post-start` to automatically scaffold and sync `.vscode/mcp.json` with explicit `env: { PATH: ... }` to `~/.gemini/config/mcp_config.json` and `.agents/mcp_config.json`. Hardened Minikube initialization with GPU detection (`nvidia-smi`), automatic fallback to CPU driver (`--driver=docker`), Docker daemon readiness verification, and automatic `minikube update-context` kubeconfig synchronization.
- **DevContainer GHCR Image Publishing Resilience**: Hardened `.github/workflows/release.yml` with lowercase GHCR repository naming and streamlined tag publication (`vX.Y.Z,latest`) to prevent 403 / `unknown blob` upload errors.

## [0.1.10] - 2026-08-18

### Added
- **Routine Tasks, Order & Methodology Guide (`docs/ROUTINE_TASKS.md`)**: Comprehensive operational manual outlining inner development loops, PR lifecycles, release orchestrations, security audit schedules, and workspace synchronization with explicit sequence ordering, frequencies, and troubleshooting matrices.
- **Strict Python 3.14 Environment Gate (`devops ci python-version`)**: Enforced standard Python 3.14+ runtime requirement across all CI quality checks and dev container configurations.
- **Actionlint & Pre-Commit Hook Integration**: Integrated [actionlint](https://github.com/rhysd/actionlint) (`actionlint-py`) into `devops ci actionlint`, `.github/workflows/ci.yml` validation pipeline, and root `.pre-commit-config.yaml` to detect GitHub Actions workflow schema discrepancies and parameter mismatches before triggering remote jobs.
- **DevContainer Pre-Build Smoke Test & Manifest Validation**: Added `devops devcontainer validate` command with JSONC comment-stripping and schema/mount/feature validation, and integrated pre-build smoke testing into `.github/workflows/ci.yml` and `.github/workflows/release.yml` prior to GHCR container registry publishing.
- **AI Review Feedback Dataset Exporter (`devops ai review export-feedback`)**: Added status-filtered JSONL dataset export (`--status INVALIDATED|VERIFIED|MITIGATED|ALL`) with rich finding metadata for prompt calibration, DPO alignment, and model fine-tuning.
- **FastAPI Service Roadmap Integration**: Defined native async FastAPI REST and OpenAPI service engine (`devops serve`) in `docs/ROADMAP.md` for remote CLI execution, AI reviews, and webhook integrations.
- **Parallel Test Execution & Worker Optimization**: Configured `--maxprocesses=4` for pytest-xdist in `pyproject.toml` and `devops ci`, reducing test suite execution time by ~4x.

### Security & Hardening
- **Path Traversal & Boundary Protection**: Enforced path containment checks across AI cache metadata (`cache.py`), outline timestamps (`outlines.py`), symlink tree walking (`repo.py`), and audit log destination paths (`audit.py`).
- **Data Confidentiality & Masking**: Redacted sensitive tokens, GitHub PATs, and PEM private keys in outline analysis and multi-agent scratchpad reasoning context.
- **SSH Key Permissions**: Implemented atomic creation of `.pub` files with restricted `0644` permissions and sanitized comment control characters.

### Changed
- **Codebase Modernization & Cleanup**: Streamlined developer and agent instruction documents (`AGENTS.md`, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`), simplified branch protection and PR merge guidelines, and cleaned documentation artifacts.

## [0.1.9] - 2026-08-18

### Added
- **OpenTofu CLI Integration (`devops tofu` / `devops tf`)**: Infrastructure-as-Code command suite automating OpenTofu initialization, planning, application, outputs, and state validation with dual `tofu`/`terraform` binary discovery.
- **Multi-Cloud Cloud Resource Modules (`tf/`)**: Production OpenTofu manifests for provisioning Kubernetes clusters and networking across AWS (EKS), Azure (AKS), and Google Cloud (GKE) tailored for deployment of project `k8s/` resources.
- **Reusable Dev Container Package Publication (GHCR)**: Integrated automated Docker Dev Container image build and publication to GitHub Container Registry (`ghcr.io/dan-petty/devops-cli/devcontainer:<version>`) on release.
- **FastMCP OpenTofu Tools & Agent Bridge**: Exposed `tf_plan`, `tf_apply`, and `tf_output` (with `tofu_*` aliases) over Model Context Protocol and bridged tools for autonomous agent execution.
- **AI Prompt Optimization & Token Density Reduction**: Optimized task directives (`review.md`, `verify_finding.md`, `chat.md`, `compose.md`, `metadata.md`) and persona domain prompts, reducing prompt overhead by ~30% while preserving strict schema invariants.
- **Roadmap & Open-Source Tooling Refresh (`docs/ROADMAP.md`)**: Chronologically ordered all release milestones and defined integrations for OpenTelemetry, Prometheus, PydanticAI, Sigstore Cosign, Semgrep, Infracost, and FastAPI.

### Changed
- **Canonical Command References**: Standardized all legacy `devops review` documentation, tests, and configuration references to `devops ai review`.
- **Python 3 Exception Tuple Invariants**: Refactored multi-exception handling to parenthesized tuples `except (Err1, Err2):` across all codebase modules.
- **Pydantic Mutable Defaults**: Enforced `Field(default_factory=...)` on all Pydantic model mutable collection defaults.

### Governance
- **Agent Branch Isolation Guidelines**: Added strict rules forbidding commits to merged or unrelated branches in `AGENTS.md`, `CONTRIBUTING.md`, and `RELEASE_CYCLE.md`.

## [0.1.8] - 2026-08-17

### Added
- **Automated Release Cycle Suite (`devops release`)**: Native release management commands (`status`, `prepare`, `check`, `notes`, `tag`) automating semver bumping, changelog entries, docs synchronization, and pre-release verification.
- **FastMCP Release Tools**: Added `release_status` MCP tool allowing autonomous AI agents to query version consistency, git tags, and documentation freshness over Model Context Protocol.
- **Automated Documentation Engine (`devops docs`)**: Dynamic CLI and FastMCP introspection engine generating markdown manuals (`CLI_REFERENCE.md`, `MCP_TOOLS.md`, `ENV_VARS.md`) and synchronizing the `README.md` Command Matrix.
- **System Architecture & SRE Governance**: Enterprise system blueprints (`ARCHITECTURE.md`), open-source governance (`LICENSE`, `CONTRIBUTING.md`), defense-in-depth threat model (`SECURITY.md`), and GitHub Actions CI/CD quality gates (`.github/workflows/ci.yml`, `.github/workflows/release.yml`).
- **Configuration & Constant Centralization**: Unified all static paths, timeouts, regex patterns, and user-facing messages in `config/constants.py`, `config/defaults.py`, and `lang/en.py`.

## [0.1.7] - 2026-08-17

### Added
- **Native DevContainer Lifecycle Engine (`devops devcontainer run-lifecycle`)**: Implemented type-safe, cross-platform Python lifecycle hooks (`--post-create`, `--post-start`, `--all`) replacing legacy shell scripts (`postCreate.sh`, `postStart.sh`).
- **Enhanced AI Reasoning Scratchpad (`ScratchpadBuffer`)**: Multi-turn reasoning scratchpad context preserving intermediate chain-of-thought, persona notes, and verification hypotheses across multi-agent review stages.
- **Prompt Token & Latency Optimization**: Compact JSON serialization (`separators=(",", ":")`), structured prompt context formatting, and reduced prompt token overhead across local Ollama and remote LLM providers.
- **Robust Worker Error Recovery**: Exception resilience in multi-agent review workers and top-level workspace `.data` directory persistence for all review sessions and metadata.
- **Dry-Run State Isolation**: Added automated test lifecycle fixture resetting dry-run state across test worker processes.

## [0.1.6] - 2026-08-12

### Added
- **SecOps Static Vulnerability Engine (`devops scan`)**: Aqua Trivy integration for vulnerability, secret, and IaC scanning with automated finding injection into `devsecops` persona reviews.
- **Kubernetes Manifest Auditor (`devops k8s lint`)**: Red Hat Kube-linter static analysis for Kubernetes manifests and Helm chart security best practices.
- **Popeye Cluster Health Sanitizer (`devops k8s audit`)**: Active Minikube and Kubernetes cluster scanning for resource limits, probe configurations, and cluster anomalies.
- **Pluto Deprecated API Scanner (`devops k8s check-deprecated`)**: Fairwinds Pluto static scanner detecting deprecated and removed Kubernetes API versions.

## [0.1.5] - 2026-08-12

### Added
- **Minikube Endpoint Auto-Detection (`devops k8s configure-urls`)**: Auto-detects Minikube NodePort service endpoints (`argocd-server`, `kube-prometheus-grafana`, `kube-prometheus-kube-prome-prometheus`) and updates `config.yaml`.
- **Validation Pipeline Integration**: Automated quality gate enforcing sequential checks (`test`, `coverage`, `lint`, `format`, `typecheck`, `audit`, `security`).
- **Active Model Display**: Explicit model backend and provider visibility for all AI review file requests.

## [0.1.4] - 2026-08-12

### Added
- **Default AI Metadata Analysis (`devops ai analyze`)**: Made `--enhanced` mode the default execution behavior across all analysis commands (`path`, `branch`, `pr`), generating 6-10 line minimalist pseudocode outlines, complexity scoring, and ISO timestamps (`last_analyzed`).
- **Incremental Analysis Caching**: Intelligent skipping of unchanged files based on `st_mtime` vs `last_analyzed` timestamps, with `--update-all` (`-u`) flag to force full metadata regeneration.
- **Submodule-Aware Dependency Scanner**: Preserved full module/submodule imports (`pydantic.v2`, `rich.console`, `devops_cli.models.ai`) in Python AST and package analysis.
- **Clean Pseudocode Generation**: Eliminated generic boilerplate language and strictly excluded import statements and package directives from pseudocode output to ensure clean separation from extracted dependencies.
- **Code Dry-Run & Core Helper Refactoring**: Added `render_dry_run_result()` in `dry_run/state.py`, `get_repo_origin_name()` in `core/repo.py`, and `get_llm_client()` in `config/settings.py`.

## [0.1.3] - 2026-08-11

### Added
- **Interactive Patch Staging (`devops ai review apply-patch --interactive`)**: Interactive unified diff rendering and confirmation before applying suggested LLM fixes.
- **Air-Gapped Ollama Model Bundler (`devops ai bundle-models`)**: Export and package local Ollama model weight manifests for air-gapped DevContainer environments.
- **Kubernetes RBAC Audit Policy Scanner (`devops k8s rbac-audit`)**: Security audit scanner evaluating RoleBindings and ServiceAccount privileges across namespaces.
- **SIEM Live Audit Streamer (`devops config audit-stream`)**: Streaming structured JSON audit trail records to Syslog or HTTP collectors.

## [0.1.2] - 2026-08-11

### Added
- **Multi-Cluster Kubeconfig Management (`devops k8s switch-context`)**: Added context switching and cluster namespace controls.
- **SIEM Audit Trail Logger (`devops_cli.core.audit`)**: Structured JSON audit trail logging (`AuditLogger`) streaming execution events to `.data/logs/audit.jsonl` or `DEVOPS_CLI_AUDIT_LOG_DEST`.
- **Automated Fix Patch Application (`devops ai review apply-patch`)**: Interactively staging suggested LLM code fixes (`finding.fix`) to target workspace source files.
- **Subcommand Dry-Run Pydantic Expansion**: Standardized `CommandDryRunResult` Pydantic models across `argo`, `grafana`, `prometheus`, `devcontainer` subcommands.

## [0.1.1] - 2026-08-11

### Added
- **Human Invalidation Feedback Exporter (`devops ai review export-feedback`)**: Export invalidated review findings (`status == "INVALIDATED"`) into JSONL benchmark datasets for prompt tuning.
- **Repository-Level Custom Team Personas (`.devops/personas/<name>.md`)**: Dynamic loading of custom reviewer persona prompts defined in `.devops/personas/` under target repositories.
- **Headless CI Ephemeral Auth (`devops config auth-headless`)**: Memory secret storage fallback for DBus-less headless Linux CI environments.
- **Line-Level GitHub PR Inline Comments (`create_pr_review_comment`)**: Line-level inline comment posting capabilities in `GitHubClient`.
- **v0.1.1 Feature Flag Configuration**: Added `FEATURE_PR_INLINE_COMMENTS`, `FEATURE_CUSTOM_PERSONAS`, and `FEATURE_HEADLESS_AUTH` canonical option constants.

## [0.1.0] - 2026-08-11

### Added
- **Codebase Metadata Analysis (`devops ai analyze`)**: Subcommand generating structured `.data/analysis/<type>-<sanitized-ref>-metadata.json` files containing project structure, dependency graphs, key symbols, and file type classification.
- **Pydantic Model Dry-Run Responses**: All subcommands in `--dry-run` mode (`review`, `analyze`, `k8s`, `docker`, `repos`, `ssh`) construct and output structured Pydantic model JSON representations (`ReviewResult`, `AnalysisMetadata`, `CommandDryRunResult`).
- **`dry_run` Submodule Package (`devops_cli.dry_run`)**: Modular package structure (`state.py`, `models.py`, `__init__.py`) providing environment-backed dry-run state tracking and response schemas.
- **Package Security Audit (`devops ci audit`)**: Added `uv audit` command and integrated dependency vulnerability scans into the standard `devops ci` quality gate pipeline.
- **`UV_MALWARE_CHECK=1` Integration**: Enabled malware scanning for `uv` package operations in `.devcontainer/devcontainer.json` and `.devcontainer/postCreate.sh`.
- **Finding Verification Pipeline**: Step 3 verification (`_validate_segment_findings`) automatically cross-references reported findings against visible source code with `VERIFIED`, `UNVERIFIED`, and `MITIGATED` status tracking.

### Changed
- **Python 3.14 Compatibility**: Standardized all exception handling clauses to parenthesized tuples `except (Err1, Err2):`.
- **Target-Agnostic Heuristics**: Refactored AI reviewer persona prompts, static analysis heuristics, and review task templates to evaluate target repositories based on their own documented conventions rather than `devops-cli` specific paths.
- **Literal Centralization**: Centralized user-facing messages, command outputs, error responses, and configuration constants in `src/devops_cli/lang/en.py` (`LanguageCatalog`) and `src/devops_cli/config/constants.py`.

### Security & Hardening
- **Path Traversal & Injection Protections**: Enforced workspace boundary checks (`_is_safe_workspace_path`, `_resolve_from_project_root`) and input sanitization against argument injection (`-` prefix validation).
- **OS Keyring Isolation**: Sensitive tokens (`github.token`, `grafana.token`, `argocd.token`, `ai.api_key`) stored exclusively in OS keyring via `keyring`.
