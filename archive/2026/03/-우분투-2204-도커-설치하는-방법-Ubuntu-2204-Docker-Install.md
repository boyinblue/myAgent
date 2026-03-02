---
title: "[우분투 22.04] 도커 설치하는 방법 (Ubuntu 22.04 Docker Install)"
url: "https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%AC-2204-%EB%8F%84%EC%BB%A4-%EC%84%A4%EC%B9%98%ED%95%98%EB%8A%94-%EB%B0%A9%EB%B2%95-Ubuntu-2204-Docker-Install"
created_at: "Tue, 13 Sep 2022 12:53:45 +0900"
event_dates:
category: ""
tags:
comments: "<p><figure class="imageblock alignCenter"><span><img height="1036" src="https://blog.kakaocdn.net/dn/bS275J/btrLTWdzQgX/M8wcxTIC89jGVGKQblardK/img.jpg" width="1109" /></span></figure>
</p>
<p>&nbsp;</p>
<p>필자는 최근에 우분투 리눅스 20.04에서 22.04로 업그레이드를 했습니다. 우분투 리눅스를 업그레이드한 이후에 여러 가지 문제들이 발생했습니다. 도어 관련 에러도 그중의 하나였습니다. 참고로 필자는 우분투 리눅스를 16.04 -&gt; 18.04 -&gt; 20.04 -&gt; 22.04로 여러 차례 업그레이드를 했는데, 도커는 16.04 버전을 사용할 때 설치했기 상당히 오래되었습니다.</p>
<p>필자의 경우는 우분투 22.04로 업그레이드한 이후에 도커를 재설치했더니 우분투 리눅스를 업그레이드하여 발생한 도커 문제들이 깔끔하게 해결되었습니다.</p>
<p>&nbsp;</p>
<hr contenteditable="false" />
<h2>1. 기존에 설치된 도커를 깨끗하게 지우는 방법</h2>
<p>Docker를 새로 설치하기 이전에 기존에 설치된 도커를 깨끗하게 지웁니다. 만약 기존에 설치된 도커가 없다면, 이 부분은 생략하시면 됩니다.</p>
<p>&nbsp;</p>
<h3>1-1. 우선 기존에 설치된 도커 제거</h3>
<pre class="bash" id="code_1663038792950"><code>$ sudo apt-get purge docker-ce
$ sudo apt-get autoclean</code></pre>
<p>apt-get purge 명령은 docker-ce 패키지만 제거를 합니다. 추가적으로 불필요해진 패키지가 발생하기 때문에 apt-get autocloean 명령을 통해서</p>
<p>&nbsp;</p>
<h3>1.2 apt에 등록된 소스 리스트 삭제</h3>
<pre class="bash" id="code_1663038936746"><code>$ sudo rm /etc/apt/sources.list.d/docker*</code></pre>
<p>apt에 등록된 소스 리스트에서 도커를 제거해줍니다. /etc/apt/sources.list.d 경로에는 docker.list, docker.list.distUpgrade, docker.list.save 등과 같은 파일들이 존재할 수 있습니다.</p>
<p>&nbsp;</p>
<h3>1.3 /etc/init/docker.conf 파일 제거</h3>
<pre class="bash" id="code_1663038988801"><code>$ sudo rm -f /etc/init/docker.conf</code></pre>
<p>/etc/init 디렉토리에는 우분투 리눅스가 부팅 시에 사용하는 설정 파일들이 존재합니다. /etc/init 디렉토리에 존재하는 docker.conf 파일을 제거합니다.</p>
<p>&nbsp;</p>
<hr contenteditable="false" />
<h2>2. 도커 설치하는 방법</h2>
<p>기존에 설치된 도커를 깨끗하게 제거했다면, 아래의 명령들을 통해서 도커를 새로 설치하시면 됩니다.</p>
<pre class="bash" id="code_1663039377467"><code>$ sudo apt-get update
$ sudo apt-get install apt-transport-https ca-certificates curl software-properties-common
$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
$ echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list &gt; /dev/null
$ sudo apt-get update
$ sudo apt install docker-ce</code></pre>
<p>&nbsp;</p>
<h2>관련 링크</h2>
<p>우분투 리눅스 22.04에 도커를 설치하는 방법에 대한 글은 아래의 영문 페이로부터 얻었습니다.</p>
<figure contenteditable="false" id="og_1663040706734"><a href="https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-22-04" rel="noopener">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">How To Install and Use Docker on Ubuntu 22.04 | DigitalOcean</p>
<p class="og-desc">&nbsp;</p>
<p class="og-host">www.digitalocean.com</p>
</div>
</a></figure>
<p>&nbsp;</p>
<p>우분투 리눅스를 22.04로 업그레이드한 이후에 "cgroups: cannot found cgroup mount destination: unknown"이라는 에러가 발생할 때 조치 방법은 아래의 글을 참고하시기 바랍니다.</p>
<figure contenteditable="false" id="og_1663040905634"><a href="https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%ACDocker-cgroups-cannot-found-cgroup-mount-destination-unknown-%EC%97%90%EB%9F%AC-%EC%A1%B0%EC%B9%98-%EB%B0%A9%EB%B2%95" rel="noopener">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">[우분투/Docker] cgroups: cannot found cgroup mount destination: unknown 에러 조치 방법</p>
<p class="og-desc">최근에 우분투 리눅스를 22.04로 업그레이드한 이후에 여러가지 문제점들이 발생하고 있습니다. 그 중에서도 기존에는 잘 실행되던 도커 이미지가 제대로 실행되지 못하는 문제가 발생했습니다.</p>
<p class="og-host">worldclassproduct.tistory.com</p>
</div>
</a></figure>
<p>&nbsp;</p>
<p>우분투 리눅스를 22.04로 업그레이드한 이후에 "cgroups: cgroup mount point does not exist: unknown"이라는 에러가 발생할 때 조치 방법은 아래의 글을 참고하시기 바랍니다.</p>
<figure contenteditable="false" id="og_1663040988141"><a href="https://worldclassproduct.tistory.com/entry/%EC%9A%B0%EB%B6%84%ED%88%AC-2204Docker-cgroup-mountpoint-does-not-exist-unknown-%ED%95%B4%EA%B2%B0-%EB%B0%A9%EB%B2%95" rel="noopener">
<div class="og-image">&nbsp;</div>
<div class="og-text">
<p class="og-title">[우분투 22.04][Docker] cgroup mountpoint does not exist: unknown 해결 방법</p>
<p class="og-desc">최근에 우분투 리눅스를 22.04로 업그레이드한 이후에 여러가지 문제점들이 발생하고 있습니다. 그 중에서도 기존에는 잘 실행되던 도커 이미지가 제대로 실행되지 못하는 문제가 발생했습니다.</p>
<p class="og-host">worldclassproduct.tistory.com</p>
</div>
</a></figure>
<p>&nbsp;</p>
<p>이상입니다.</p>
<p>&nbsp;</p>
<p>&nbsp;</p>"
keywords:
crawler_version: "2.2"
images:
---

# [우분투 22.04] 도커 설치하는 방법 (Ubuntu 22.04 Docker Install)

(본문 없음)