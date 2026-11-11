# The maintained actionlint fork (#1501) that knows current runner labels, pinned by digest.
# This stage is a reference only; the binary is copied into the devcontainer image below.
FROM docker.io/kjanat/actionlint:1.17.0@sha256:d484cccadf56b6a356466ade9af4c8e05c5dce1badaf0a9ecd0d7639d68d9c92 AS actionlint

# The binary tools of the image, each at an exact version with the sha256 of its build for the
# platform. The stage downloads and checks them and keeps the commands in /out/bin, so curl and
# unzip are not in the image and a source change of this repository rebuilds no step of it.
FROM debian:sid AS tools
ARG TARGETARCH
ARG DEBIAN_FRONTEND=noninteractive
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    unzip \
    && mkdir -p /out/bin

# kubectl 1.37.2
RUN case "$TARGETARCH" in \
      amd64) url='https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/kubectl'; sha='c04487523e7aa7d1493f7808174c899db93d7a9cf57531420cd76b9bd415f8f4'; member='' ;; \
      arm64) url='https://dl.k8s.io/release/v1.37.2/bin/linux/arm64/kubectl'; sha='fcc16f63186659d9722014b7e02d5fdd2d4e669cb8c0ab66365d7d3b8ba03509'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    install -m 0755 /tmp/asset /out/bin/kubectl && \
    rm -rf /tmp/asset /tmp/unpack

# kustomize 5.8.3
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v5.8.3/kustomize_v5.8.3_linux_amd64.tar.gz'; sha='cb9e31198d3f63b44848bd0afc4c8efc56e6cfef9c93a4a39a211940e6decd61'; member='kustomize' ;; \
      arm64) url='https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize/v5.8.3/kustomize_v5.8.3_linux_arm64.tar.gz'; sha='9867b76482cfc6d25b546abc1d2b5a32bd137505aba640649b4b378f64f6d68f'; member='kustomize' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/kustomize && \
    rm -rf /tmp/asset /tmp/unpack

# helm 4.3.1
RUN case "$TARGETARCH" in \
      amd64) url='https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz'; sha='0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b'; member='linux-amd64/helm' ;; \
      arm64) url='https://get.helm.sh/helm-v4.3.1-linux-arm64.tar.gz'; sha='8cf8f66ecbc252ac8f7f06cca68aba88508ddfde3a6a34feb1678ad1694b4f88'; member='linux-arm64/helm' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/helm && \
    rm -rf /tmp/asset /tmp/unpack

# argo 4.1.5
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/argoproj/argo-workflows/releases/download/v4.1.5/argo-linux-amd64.gz'; sha='ab78728d3bcd029f0e8547736e2f3c69d2519a134a3f9ee74454ededa14af36c'; member='' ;; \
      arm64) url='https://github.com/argoproj/argo-workflows/releases/download/v4.1.5/argo-linux-arm64.gz'; sha='70058ede05677ae1d173bc9de8c670f01e21284dbbc0da1c5434217208a5c5eb'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    gunzip -c /tmp/asset > /out/bin/argo && chmod 0755 /out/bin/argo && \
    rm -rf /tmp/asset /tmp/unpack

# argocd 3.5.4
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/argoproj/argo-cd/releases/download/v3.5.4/argocd-linux-amd64'; sha='9cd8cb9f8f785357af441a9544cc1c63a2b8d9bad45ebe88503ab8e315c64ae3'; member='' ;; \
      arm64) url='https://github.com/argoproj/argo-cd/releases/download/v3.5.4/argocd-linux-arm64'; sha='fe7c737ac912e281fa13dc27b2be6695634b9fe483d52846f3e7e65067b11c12'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    install -m 0755 /tmp/asset /out/bin/argocd && \
    rm -rf /tmp/asset /tmp/unpack

# cloudflared 2026.10.4
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/cloudflare/cloudflared/releases/download/2026.10.4/cloudflared-linux-amd64'; sha='ae5e8add7884b0531d66bbca4570d1de491ff6da51e4ebe7eb160cdf241d9e42'; member='' ;; \
      arm64) url='https://github.com/cloudflare/cloudflared/releases/download/2026.10.4/cloudflared-linux-arm64'; sha='2b7203b4fb0ba28a0c1e12f8855ce2c25f76d266a8d5edafac5540b6812acff6'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    install -m 0755 /tmp/asset /out/bin/cloudflared && \
    rm -rf /tmp/asset /tmp/unpack

# kubectl-argo-rollouts 1.10.0
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/argoproj/argo-rollouts/releases/download/v1.10.0/kubectl-argo-rollouts-linux-amd64'; sha='57a464e80c3e716076c9760e1d15ff06b853e3bcab3e22e30f4dba8a3e9f29b2'; member='' ;; \
      arm64) url='https://github.com/argoproj/argo-rollouts/releases/download/v1.10.0/kubectl-argo-rollouts-linux-arm64'; sha='2d73e61091084769d16191f21fc686b9c2054892eb93d59046660e8c876a6865'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    install -m 0755 /tmp/asset /out/bin/kubectl-argo-rollouts && \
    rm -rf /tmp/asset /tmp/unpack

# trivy 0.75.0
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/aquasecurity/trivy/releases/download/v0.75.0/trivy_0.75.0_Linux-64bit.tar.gz'; sha='c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f'; member='trivy' ;; \
      arm64) url='https://github.com/aquasecurity/trivy/releases/download/v0.75.0/trivy_0.75.0_Linux-ARM64.tar.gz'; sha='a1ee9f6ffb7d112b64ff726a2a0717c21175c1114361391f4a132956751a13b3'; member='trivy' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/trivy && \
    rm -rf /tmp/asset /tmp/unpack

# kube-linter 0.8.3
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/stackrox/kube-linter/releases/download/v0.8.3/kube-linter-linux'; sha='618d299a3e2839c8ca9d86fce0db617be0fba41f0fecbbbfb7fbf1c04299fae1'; member='' ;; \
      arm64) url='https://github.com/stackrox/kube-linter/releases/download/v0.8.3/kube-linter-linux_arm64'; sha='9c39d35252e0dcafb16b26197b9e93ba578e44eb402c3c6660fc94e08f94094f'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    install -m 0755 /tmp/asset /out/bin/kube-linter && \
    rm -rf /tmp/asset /tmp/unpack

# popeye 0.22.1
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/derailed/popeye/releases/download/v0.22.1/popeye_linux_amd64.tar.gz'; sha='d58a3c0ba45805d452c32628320eecdcb5172fd5f42c82e12aeecc7a17eb930b'; member='popeye' ;; \
      arm64) url='https://github.com/derailed/popeye/releases/download/v0.22.1/popeye_linux_arm64.tar.gz'; sha='5188b0b521966113580f0fef7769173af6303061dee10df247536f9bb55fe988'; member='popeye' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/popeye && \
    rm -rf /tmp/asset /tmp/unpack

# pluto 5.24.4
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/FairwindsOps/pluto/releases/download/v5.24.4/pluto_5.24.4_linux_amd64.tar.gz'; sha='1e5077ce1016fb0bb8ce0103c12b7ca8666eb3959d787ecfc95d9b8acd507147'; member='pluto' ;; \
      arm64) url='https://github.com/FairwindsOps/pluto/releases/download/v5.24.4/pluto_5.24.4_linux_arm64.tar.gz'; sha='46afed19dec949bd9f7c1da0422ce9d1bdb22c15ae8441552374642ac72f0882'; member='pluto' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/pluto && \
    rm -rf /tmp/asset /tmp/unpack

# kubeconform 0.8.0
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-linux-amd64.tar.gz'; sha='9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883'; member='kubeconform' ;; \
      arm64) url='https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-linux-arm64.tar.gz'; sha='1f53fc8e81258197a35e8603054162a5af1de8c5af13746c71ab680d9534ed87'; member='kubeconform' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/kubeconform && \
    rm -rf /tmp/asset /tmp/unpack

# tflint 0.65.0
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/terraform-linters/tflint/releases/download/v0.65.0/tflint_linux_amd64.zip'; sha='d4c545ed2e29d6338604b586f34f544f380f70f243aa72f7b484713835eaec61'; member='tflint' ;; \
      arm64) url='https://github.com/terraform-linters/tflint/releases/download/v0.65.0/tflint_linux_arm64.zip'; sha='843017c47a98be1de4d88fa038daa293770fe25cd01656c4f08b2e30d1d3b3a0'; member='tflint' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    unzip -q /tmp/asset "$member" -d /tmp/unpack && install -m 0755 "/tmp/unpack/$member" /out/bin/tflint && \
    rm -rf /tmp/asset /tmp/unpack

# k9s 0.51.0
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/derailed/k9s/releases/download/v0.51.0/k9s_Linux_amd64.tar.gz'; sha='c3752ad51a5a4015a113819c4eeb6e55a4d0e4b8e652494797532f6fc8161dd7'; member='k9s' ;; \
      arm64) url='https://github.com/derailed/k9s/releases/download/v0.51.0/k9s_Linux_arm64.tar.gz'; sha='3ee05c82e5f9198928a4e86133608ba6a2c10a2244d6a7789e820f78319d640c'; member='k9s' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/k9s && \
    rm -rf /tmp/asset /tmp/unpack

# gh-dash 4.26.2
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/dlvhdr/gh-dash/releases/download/v4.26.2/gh-dash_v4.26.2_linux-amd64'; sha='565d7dbfafc568c06441ab49d31c7059b7ade7cbba12490fa7f12f9bb71dc1b5'; member='' ;; \
      arm64) url='https://github.com/dlvhdr/gh-dash/releases/download/v4.26.2/gh-dash_v4.26.2_linux-arm64'; sha='67e55fe550e86dc7555979f8e0d05b88e1ba086b022a6e19e071dfc67369ec50'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    install -m 0755 /tmp/asset /out/bin/gh-dash && \
    rm -rf /tmp/asset /tmp/unpack

# tuicr 0.27.0
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/agavra/tuicr/releases/download/v0.27.0/tuicr-0.27.0-x86_64-unknown-linux-musl.tar.gz'; sha='f673ff709af2501c111216c95745395ae2bfedf3daa3d039539f9614a6ddb4e4'; member='tuicr' ;; \
      arm64) url='https://github.com/agavra/tuicr/releases/download/v0.27.0/tuicr-0.27.0-aarch64-unknown-linux-musl.tar.gz'; sha='d0707f491cc8cdf0930fc1466029341d804a0105dd0b674f8dca33afb8366490'; member='tuicr' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/tuicr && \
    rm -rf /tmp/asset /tmp/unpack

# gitleaks 8.30.1
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz'; sha='551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'; member='gitleaks' ;; \
      arm64) url='https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_arm64.tar.gz'; sha='e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080'; member='gitleaks' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/gitleaks && \
    rm -rf /tmp/asset /tmp/unpack

# osv-scanner 2.6.0
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/google/osv-scanner/releases/download/v2.6.0/osv-scanner_linux_amd64'; sha='ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108'; member='' ;; \
      arm64) url='https://github.com/google/osv-scanner/releases/download/v2.6.0/osv-scanner_linux_arm64'; sha='2c71403eb443d05891c4f268c3ad771cf4f16e5443463fd7851ef8f454d3c7e4'; member='' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    install -m 0755 /tmp/asset /out/bin/osv-scanner && \
    rm -rf /tmp/asset /tmp/unpack

# golangci-lint 1.64.6
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/golangci/golangci-lint/releases/download/v1.64.6/golangci-lint-1.64.6-linux-amd64.tar.gz'; sha='71e290acbacb7b3ba4f68f0540fb74dc180c4336ac8a6f3bdcd7fcc48b15148d'; member='golangci-lint-1.64.6-linux-amd64/golangci-lint' ;; \
      arm64) url='https://github.com/golangci/golangci-lint/releases/download/v1.64.6/golangci-lint-1.64.6-linux-arm64.tar.gz'; sha='99a7ff13dec7a8781a68408b6ecb8a1c5e82786cba3189eaa91d5cdcc24362ce'; member='golangci-lint-1.64.6-linux-arm64/golangci-lint' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/golangci-lint && \
    rm -rf /tmp/asset /tmp/unpack

# promtool 3.15.1
RUN case "$TARGETARCH" in \
      amd64) url='https://github.com/prometheus/prometheus/releases/download/v3.15.1/prometheus-3.15.1.linux-amd64.tar.gz'; sha='6a726885328ad9efebbf36e876ce2fb6225468a71fd1e7ce3ba666d5f4d97a84'; member='prometheus-3.15.1.linux-amd64/promtool' ;; \
      arm64) url='https://github.com/prometheus/prometheus/releases/download/v3.15.1/prometheus-3.15.1.linux-arm64.tar.gz'; sha='ceb6d21493c37ca0b4513b147642797c68cf39a0f50a444d50e1e80c74f21b26'; member='prometheus-3.15.1.linux-arm64/promtool' ;; \
    esac && \
    mkdir -p /tmp/unpack && \
    curl -fsSL --retry 3 -o /tmp/asset "$url" && \
    echo "$sha  /tmp/asset" | sha256sum -c - && \
    tar -xzf /tmp/asset -C /tmp/unpack "$member" && install -m 0755 "/tmp/unpack/$member" /out/bin/promtool && \
    rm -rf /tmp/asset /tmp/unpack

# The Node tools of the image. `npm ci` installs from the committed lockfile, which npm checks
# against the sha512 of every package, and `--ignore-scripts` runs no install script. The stage
# keeps only the installed folders: the Node feature of the image configuration provides the
# runtime that the commands use at run time.
FROM node:24-trixie-slim@sha256:54f84b4cf8432b21aaffd5d3ce8d41e12cea0d10d33c09d2f3c9879d49d6b446 AS npm-tools
COPY src/devops_cli/tools_lock/openspec/package.json src/devops_cli/tools_lock/openspec/package-lock.json /opt/openspec/
RUN cd /opt/openspec && npm ci --ignore-scripts
COPY src/devops_cli/tools_lock/devcontainers-cli/package.json src/devops_cli/tools_lock/devcontainers-cli/package-lock.json /opt/devcontainers-cli/
RUN cd /opt/devcontainers-cli && npm ci --ignore-scripts
# Style Dictionary builds the design tokens (`make design-tokens`, docs/DESIGN.md). Its lock is no
# entry of tools.lock: Renovate updates it.
COPY src/devops_cli/tools_lock/style-dictionary/package.json src/devops_cli/tools_lock/style-dictionary/package-lock.json /opt/style-dictionary/
RUN cd /opt/style-dictionary && npm ci --ignore-scripts

FROM debian:sid

# Avoid interactive prompts during apt operations in CI
ARG DEBIAN_FRONTEND=noninteractive

# Optimize Python runtime and uv execution in containerized environments
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    TIKTOKEN_CACHE_DIR=/usr/local/share/tiktoken

# Install Python 3.14 runtime, symlinks, root certificates, and the gnome-keyring Secret Service
# (dbus-x11 satisfies its session-bus dependency without pulling in systemd) with BuildKit apt
# cache mounts. /run/user/1000 holds the container-local session bus; /tmp is shared.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    python3.14 \
    python-is-python3 \
    ca-certificates \
    shellcheck \
    gnome-keyring \
    dbus-x11 \
    bubblewrap \
    socat \
    && install -d -m 0700 -o 1000 -g 1000 /run/user/1000 \
    && sed -i 's/VERSION_CODENAME=forky/VERSION_CODENAME=trixie/' /etc/os-release \
    && rm -rf /var/lib/apt/lists/*

# Install standalone uv and uvx binaries into /usr/local/bin pinned to release
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /usr/local/bin/

# The tools of the image, in the places the Filesystem Hierarchy Standard names for software that
# the administrator installs: the commands are in /usr/local/bin, which PATH holds already, and the
# files of a Python or Node tool are in /usr/local/share/devops-tools. All of it is root-owned and
# outside the home volume, so a rebuild of the image is the way to change a tool.
COPY --from=tools /out/bin/ /usr/local/bin/
COPY --from=npm-tools /opt/openspec /usr/local/share/devops-tools/openspec
COPY --from=npm-tools /opt/devcontainers-cli /usr/local/share/devops-tools/devcontainers-cli
COPY --from=npm-tools /opt/style-dictionary /usr/local/share/devops-tools/style-dictionary
RUN ln -s ../share/devops-tools/openspec/node_modules/.bin/openspec /usr/local/bin/openspec && \
    ln -s ../share/devops-tools/devcontainers-cli/node_modules/.bin/devcontainer /usr/local/bin/devcontainer && \
    ln -s ../share/devops-tools/style-dictionary/node_modules/.bin/style-dictionary /usr/local/bin/style-dictionary

# Python tools install into a virtual environment of their own from the hashed requirements file,
# and `--require-hashes` refuses a distribution that the file does not name.
COPY src/devops_cli/tools_lock/semgrep.txt /tmp/tools_lock/semgrep.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv --python /usr/bin/python3.14 /usr/local/share/devops-tools/semgrep && \
    uv pip sync --require-hashes -p /usr/local/share/devops-tools/semgrep/bin/python /tmp/tools_lock/semgrep.txt && \
    ln -s /usr/local/share/devops-tools/semgrep/bin/semgrep /usr/local/share/devops-tools/semgrep/bin/pysemgrep /usr/local/bin/ && \
    rm -rf /tmp/tools_lock/semgrep.txt
COPY src/devops_cli/tools_lock/bandit.txt /tmp/tools_lock/bandit.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv --python /usr/bin/python3.14 /usr/local/share/devops-tools/bandit && \
    uv pip sync --require-hashes -p /usr/local/share/devops-tools/bandit/bin/python /tmp/tools_lock/bandit.txt && \
    ln -s /usr/local/share/devops-tools/bandit/bin/bandit /usr/local/bin/ && \
    rm -rf /tmp/tools_lock/bandit.txt

# Pre-install dependencies from lockfile for optimal Docker layer caching in CI
COPY pyproject.toml uv.lock /tmp/devops-cli/
RUN --mount=type=cache,target=/root/.cache/uv \
    cd /tmp/devops-cli && \
    uv export --no-dev --extra review --no-emit-project -o /tmp/requirements.txt && \
    uv pip install --system --break-system-packages -r /tmp/requirements.txt pre-commit && \
    python3 -c "import tiktoken; tiktoken.get_encoding('cl100k_base'); tiktoken.get_encoding('o200k_base')" && \
    rm -rf /tmp/requirements.txt

# Copy devops-cli source files and install the package without re-downloading dependencies.
# This copy is the devops of the published image: a child repository's post-create and
# post-start run it, and so does this repository's first post-create, before `uv sync` fills
# .venv. The remoteEnv PATH of .devcontainer/devcontainer.json puts .venv/bin first, so in this
# repository `devops` is the editable install of the checkout (#2449).
COPY pyproject.toml README.md /tmp/devops-cli/
COPY src/ /tmp/devops-cli/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages --no-deps /tmp/devops-cli && \
    rm -rf /tmp/devops-cli

# Provide the pinned actionlint binary on PATH so the bare `actionlint` command resolves.
# Placed last so a source change above rebuilds no earlier layer.
COPY --from=actionlint /usr/local/bin/actionlint /usr/local/bin/actionlint
