---
title: "파이썬 스크립트 자동실행 방법 (#!/usr/bin/env python3)"
url: "https://worldclassproduct.tistory.com/entry/%ED%8C%8C%EC%9D%B4%EC%8D%AC-%EC%8A%A4%ED%81%AC%EB%A6%BD%ED%8A%B8-%EC%9E%90%EB%8F%99%EC%8B%A4%ED%96%89-%EB%B0%A9%EB%B2%95-usrbinenv-python3"
created_at: "Tue, 27 Sep 2022 00:38:57 +0900"
event_dates:
category: ""
tags:
comments: "<p><figure class="imageblock alignCenter"><span><img height="725" src="https://blog.kakaocdn.net/dn/clJgXB/btrM5QDKJhh/JFx4VJXt9iUpQQbYKTms20/img.png" width="786" /></span></figure>
</p>
<p>파이썬을 처음 시작했을 때는 파이썬 스크립트를 실행시킬 때마다 python 혹은 python3 명령을 붙여주었다. 하지만 파이썬에 어느 정도 익숙해진 지금은 shebang(셔뱅)을 이용해서 파이썬 스크립트를 자동으로 실행될 수 있도록 작성하고 있다.&nbsp;</p>
<p>&nbsp;</p>
<h2>셔뱅(shebang)이란?</h2>
<p>셔뱅(shebang)이라는 것이 처음에는 조금 낯설 수 있겠다. 하지만 우리는 이미 습관적으로 셔뱅을 구사하고 있다. 우리가 bash script를 작성할 때 아주 습관적으로 가장 첫 번째 줄에 #!/bin/bash를 입력한다. 마찬가지로 파이썬 스크립트에 #!/usr/bin/env python3 구문을 입력하면 쉘은 알아서 python3를 실행하여 해당 스크립트를 수행한다.&nbsp;</p>
<p>&nbsp;</p>
<h3>배쉬 스크립트 셔뱅 예제 (script.sh)</h3>
<pre class="bash" id="code_1664205769763"><code>#!/bin/bash
set -e -x

TEMP_FILE=$(tempfile)

function print_usage()
{
  set +x
  echo "Send e-mail"
  echo "(Usage) ${0} -body=(content file path) -header=(email_header) -email=(whole email path)"
  echo "(Example) ${0} -body=tmp/list.html -header=tmp/email_header.txt -email=tmp/email.txt"
}</code></pre>
<p>위의 스크립트를 살펴보면 배쉬 스크립트가 "#!/bin/bash"로 시작하는 것을 알 수 있다. 즉, 이 스크립트를 ./script.sh로 실행한다는 것은 /bin/bash script.sh 명령으로 실행되는 것과 동일(equivalent)하다. 즉, /bin/bash script.sh로 복잡하게 실행하지 않고, ./script.sh로 간단하게 실행시킬 수 있다는 의미이다.&nbsp;</p>
<p>&nbsp;</p>
<h3>파이썬 스크립트 셔뱅 예제 (초급)</h3>
<pre class="python" id="code_1664206159024"><code>#!/usr/bin/python3

import os
from PIL import Image, ImageDraw, ImageFont
  
# create Image object
text1 = None
text2 = None
img_name = None

logo_fname = ''
background_fname = ''
font = ''
target_dir = ''</code></pre>
<p>위의 파이썬 스크립트는 #!/usr/bin/python3로 시작한다. ./script.py 명령으로 해당 스크립트를 python3 프로그램을 자동으로 실행할 수 있다. 하지만, 이런 방법은 좋은 방법이 아니다. 왜냐하면 python3 프로그램의 경로가 꼭 /usr/bin/python3가 아닐 수도 있기 때문이다.&nbsp;</p>
<p>&nbsp;</p>
<h3>파이썬 스크립트 셔뱅 예제 (고급)</h3>
<pre class="python" id="code_1664205887800"><code>#!/usr/bin/env python3

import os
from PIL import Image, ImageDraw, ImageFont
  
# create Image object
text1 = None
text2 = None
img_name = None

logo_fname = ''
background_fname = ''
font = ''
target_dir = ''</code></pre>
<p>위의 파이썬 스크립트는 "#!/usr/bin/env python3"로 시작하는 것을 알 수 있다. 방금 전의 예제와 비슷하지만 조금 다르다. env python3 명령이 알아서 python3 프로그램의 경로를 찾아서 알아서 스크립트를 실행시켜주기 때문이다. 따라서 python3 패키지가 /usr/bin/python3 위치에 있지 않아도 문제없이 실행된다.&nbsp;</p>
<p>&nbsp;</p>
<h2>잊지 말자! 실행 권한 부여!</h2>
<p>만약 실행 권한을 부여하지 않고 스크립트를 수행하면 아래와 같은 에러 메시지를 토해내면서 제대로 실행되지 않는다.</p>
<table border="1" style="border-collapse: collapse; width: 100%;">
<tbody>
<tr>
<td style="width: 100%;">$ ./script.py<br /><span style="color: #ee2323;"><b>-bash: ./script.py: 허가 거부</b></span></td>
</tr>
</tbody>
</table>
<p>&nbsp;</p>
<p>셔뱅을 활용한 배쉬 스크립트도 실행을 위해서는 실행 권한을 부여해야 한다. 셔뱅을 활용한 파이썬 스크립트 역시도 마찬가지이다. 아래의 명령으로 반드시 실행 권한을 부여하자!&nbsp;</p>
<pre class="python" id="code_1664206465418"><code>$ chmod +x script.py</code></pre>
<p>&nbsp;</p>
<p>실행 권한을 추가하면 ./script.py 명령으로 손쉽게 파이썬 스크립트를 실행시킬 수 있다.&nbsp;</p>
<p>&nbsp;</p>
<p>이상입니다.&nbsp;</p>
<p>&nbsp;</p>
<p>&nbsp;</p>"
keywords:
crawler_version: "2.2"
images:
---

# 파이썬 스크립트 자동실행 방법 (#!/usr/bin/env python3)

(본문 없음)