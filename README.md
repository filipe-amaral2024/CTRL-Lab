# CRTL-Lab — Controle de Acesso e Segurança para Laboratórios

## 1. Visão geral

O **CTRL-Lab** é um protótipo acadêmico de controle de acesso e monitoramento de segurança para laboratórios, desenvolvido para a feira de Computação.

A proposta combina **visão computacional, inteligência artificial, sensores ambientais e automação** para auxiliar na prevenção e identificação de situações de risco em um laboratório.

O projeto usa uma câmera **PS3 Eye** conectada por USB ao Raspberry Pi, sensores ambientais e inferência local. Sem parâmetros, `start-ctrlab.ps1` inicia **pré-visualização sem IA**. Um modelo de pessoa/jaleco foi treinado e avaliado localmente, mas os pesos ONNX ficam em `runs/` e não são versionados; forneça-os com `-AccessModel` para ativar a detecção. A integração física e o desempenho do modelo ainda precisam ser validados na montagem final do Pi. Consulte [Funcionamento atual](docs/FUNCIONAMENTO_ATUAL.md), [Apresentação do projeto](docs/APRESENTACAO_PROJETO.md) e [Pendências para concluir](docs/PENDENCIAS_CONCLUSAO.md).

---

## 2. Objetivos

### Objetivo geral

Desenvolver um sistema capaz de verificar condições básicas de segurança no acesso e no ambiente de um laboratório, utilizando visão computacional e sensores para identificar situações inadequadas ou potencialmente perigosas.

### Objetivos específicos

- Detectar pessoas na entrada do laboratório.
- Verificar o uso dos principais equipamentos de proteção individual (EPIs).
- Identificar situações de EPI inadequado e gerar alertas.
- Monitorar fumaça e fogo continuamente pela PS3 Eye compartilhada.
- Habilitar/desabilitar a análise de acesso sem interromper a checagem de segurança.
- Detectar visualmente fumaça e possíveis sinais de incêndio.
- Integrar sensores ambientais ao sistema.
- Exibir o estado pelo dashboard; o buzzer físico toca somente em `EMERGENCY`.
- Pausar câmera/visão durante uma emergência, mantendo Raspberry Pi, botões, buzzer de emergência e MQTT ativos para permitir reset e monitoramento.
- Registrar eventos e ocorrências.
- Disponibilizar uma interface para acompanhamento do sistema.
- Demonstrar a integração entre inteligência artificial, software, sensores e sistemas embarcados.

---

## 3. Funcionalidades propostas

> **Escopo atual da apresentação:** visão computacional limitada a pessoa/jaleco, exigindo somente jaleco. Fogo/fumaça por visão permanece opcional; sensores físicos continuam como camada separada. A entrada atualmente implementada para gás é o DO digital do MQ-2.

### 3.1 Controle de acesso

A câmera única ficará posicionada de forma que o mesmo enquadramento possa ser usado pelos modelos de segurança e acesso.

O sistema deverá:

1. Detectar a presença de uma pessoa.
2. Analisar a imagem.
3. Identificar os EPIs necessários.
4. Verificar se os requisitos de segurança foram atendidos.
5. Informar se o acesso está:
   - `PERMITIDO`
   - `ALERTA — EPI INADEQUADO`

Os requisitos do laboratório são:

- Jaleco.
- Calça.
- Tênis/calçado fechado.
- Cabelo amarrado somente quando comprido.

> O objetivo é verificar condições de segurança, e não identificar a identidade da pessoa. O projeto não depende de reconhecimento facial.

---

### 3.2 Segurança contínua

O modelo de segurança deve permanecer ativo durante toda a execução visual e será utilizado para:

- Identificação visual de fumaça.
- Identificação visual de possíveis chamas/incêndios.
- Geração de eventos de alerta ou emergência.

### 3.3 Modos de execução

| Modelo | Estado inicial | Controle |
|---|---|---|
| Segurança (fumaça/fogo) | Sempre ativo | Não pode ser desligado pelo dashboard ou teclado |
| Acesso (pessoa/EPI) | Desabilitado | Tecla `A` no terminal ou comando MQTT do dashboard |

Ao desabilitar o modelo de acesso, a câmera e o modelo de segurança continuam funcionando. Durante uma emergência, o runtime pausa câmera e visão e mantém o buzzer acionado, assim como sensores, botões, Raspberry Pi e telemetria. O reset inicia uma nova verificação de segurança; a operação só retorna após uma inferência segura e a ausência de riscos críticos.

---

### 3.4 Sensores ambientais

O Raspberry Pi 3B+ poderá receber dados de sensores como:

- Temperatura.
- Umidade.
- Gases.
- Partículas/fumaça, caso disponível.

Os sensores físicos complementam a visão computacional.

Uma câmera, por exemplo, não consegue detectar diretamente um gás invisível. Para isso, é necessário utilizar um sensor apropriado.

---

### 3.5 Sistema de alertas

Quando uma situação inadequada for detectada, o sistema poderá:

- Exibir um alerta no computador.
- Acionar o buzzer somente em `EMERGENCY`; estados `WARNING`/`ALERT`, incluindo a detecção de pessoa sem jaleco, permanecem visuais/telemetrizados e não tocam o buzzer.
- Registrar o evento.
- Alterar o estado do sistema para `ALERTA` ou `EMERGÊNCIA`.

---

## 4. Arquitetura do sistema

```text
PS3 Eye USB ──► Raspberry Pi 3B+
                    │ Um frame compartilhado
                    ├── Modelo segurança (sempre ativo)
                    ├── Modelo acesso (alternável)
                    ├── Sensores + alarmes
                    └── MQTT ──► Computador (dashboard web + SQLite)
```

### Divisão das responsabilidades

**PS3 Eye**
- Captura local de vídeo por USB.
- Um único frame por ciclo compartilhado pelos dois modelos.

**Notebook/Computador**
- Dashboard web acessível pelo navegador via IP na rede local.
- Pode alternar o modelo de acesso via MQTT, com token de controle.
- Recepção de status e eventos via MQTT.
- Histórico local de eventos em SQLite.

**Raspberry Pi 3B+**
- Captura da PS3 Eye e execução dos modelos ONNX em CPU.
- Mantém segurança contínua mesmo quando a análise de acesso está desabilitada.
- Análise de EPIs e detecção visual de fumaça/incêndio.
- Leitura dos sensores.
- Controle do buzzer somente em `EMERGENCY`; durante esse estado, câmera/visão são pausadas.
- Decisão e acionamento local dos alertas, sem depender do computador.

---

## 5. Tecnologias previstas

### Software

- Python
- OpenCV DNN (inferência CPU no Raspberry)
- YOLOv8 exportado em ONNX
- MQTT
- SQLite
- FastAPI ou Flask
- HTML/CSS/JavaScript
- Git/GitHub

### Hardware

- Raspberry Pi 3B+
- Uma câmera PS3 Eye USB
- Sensores ambientais
- Resistores
- Buzzer
- Botão de emergência/reset
- Fonte e componentes de prototipagem

---

## 6. Inteligência artificial

O projeto não pretende desenvolver uma rede neural do zero. O Raspberry executa modelos YOLOv8 ONNX pelo OpenCV DNN, em CPU, sobre frames da PS3 Eye. Para a demonstração com prazo curto, o escopo visual é pessoa/jaleco e pode funcionar sem um modelo de fogo/fumaça. Se ambos forem configurados, segurança visual roda continuamente e o acesso inicia desabilitado. Os sensores físicos configurados continuam independentes da visão.

Serão utilizadas bibliotecas e modelos existentes, principalmente:

- **OpenCV DNN** para inferência local com o modelo YOLOv8 ONNX.
- **Ultralytics**, opcional na máquina de desenvolvimento, para exportar modelos treinados.

Os modelos são arquivos ONNX separados, com listas de classes próprias. O detector de acesso aceita o perfil legado `person,lab_coat` ou as classes `person_with_labcoat,person_without_labcoat` do dataset Roboflow v12. O detector `smoke,fire` é opcional para segurança visual.

O dataset Roboflow v12 é segmentado; `python .\tools\prepare_labcoat_dataset.py` gera uma cópia local de detecção com caixas YOLO para treinamento, sem alterar os polígonos originais. Instruções de treino, validação e exportação estão no [guia de execução](docs/GUIA_EXECUCAO.md). O repositório não contém pesos treinados.

Quando executado sozinho, o modelo de pessoa/jaleco começa habilitado e pode ser pausado/reativado pelo atalho `A` no terminal ou pelo dashboard via MQTT. Quando segurança visual também está configurada, o acesso começa desabilitado; o seu controle nunca desativa a checagem de segurança.

### Possíveis classes do modelo de acesso/EPI

```text
person_with_labcoat
person_without_labcoat
```

O fluxo com essas classes avalia diretamente o status de cada pessoa; `person_with_labcoat` é permitido e `person_without_labcoat` gera alerta. O perfil legado `person,lab_coat` ainda associa as caixas do jaleco à pessoa pela posição. Calça, calçado e cabelo não são requisitos do escopo atual de apresentação.

### Possíveis classes do modelo contínuo de segurança

```text
fire
smoke
```

A IA será responsável por responder:

> "O que aparece na imagem?"

Uma camada de software separada será responsável por responder:

> "O que essa detecção significa para a segurança do laboratório?"

Exemplo:

```text
Detecções:
- Jaleco: SIM
- Calça: SIM
- Calçado fechado: NÃO
- Cabelo comprido: SIM
- Cabelo preso: NÃO

Resultado:
ACESSO EM ALERTA
Motivo:
Calçado fechado ausente
```

---

## 7. Estados do sistema

O sistema poderá trabalhar com três estados principais:

```text
NORMAL
   │
   ├── EPI inadequado ──► ALERTA
   │                         │
   │                         └── EPI corrigido ──► NORMAL
   │
   └── Fumaça/Fogo/Gás ──► EMERGÊNCIA
```

### NORMAL

Nenhuma condição de risco identificada.

### ALERTA

Existe uma condição que exige atenção, mas não necessariamente uma emergência.

Exemplo:

- Pessoa sem calça ou calçado fechado; cabelo comprido sem estar preso.
- Pessoa sem jaleco.

### EMERGÊNCIA

Existe uma situação potencialmente perigosa.

Exemplo:

- Incêndio.
- Grande quantidade de fumaça.
- Concentração perigosa de gás.
- Temperatura anormal, dependendo do sensor utilizado.

---

## 8. Registro de eventos

Os eventos poderão ser armazenados em um banco SQLite.

Exemplo:

| Data/Hora | Tipo | Descrição | Estado |
|---|---|---|---|
| 10:30 | EPI | Pessoa sem jaleco | ALERTA |
| 10:42 | EPI | Acesso permitido | NORMAL |
| 11:05 | FUMAÇA | Fumaça detectada | EMERGÊNCIA |
| 11:06 | SENSOR | Temperatura elevada | EMERGÊNCIA |

Isso permitirá demonstrar o histórico de ocorrências durante a apresentação.

---

## 9. Estrutura inicial do projeto

```text
CRTL-Lab/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── cameras/
│   │   └── entry_camera.py
│   │
│   ├── vision/
│   │   ├── person.py
│   │   ├── ppe.py
│   │   └── fire.py
│   │
│   ├── sensors/
│   │   ├── gas.py
│   │   ├── temperature.py
│   │   └── smoke.py
│   │
│   ├── safety/
│   │   ├── decision.py
│   │   └── alerts.py
│   │
│   ├── communication/
│   │   ├── mqtt_client.py
│   │   └── messages.py
│   │
│   ├── database/
│   │   └── database.py
│   │
│   └── web/
│       ├── app.py
│       ├── templates/
│       └── static/
│
├── models/
│   ├── ppe/
│   └── fire/
│
├── tests/
│
├── requirements.txt
├── PLANO_DESENVOLVIMENTO.md
└── README.md
```

Projeto do Raspberry:

```text
raspberry/
├── main.py
├── mqtt_client.py
│
├── sensors/
│   ├── gas.py
│   ├── temperature.py
│   └── smoke.py
│
└── actuators/
    ├── leds.py
    ├── buzzer.py
    └── siren.py
```

---

## 10. Resultado esperado

Ao final do projeto, espera-se obter um protótipo funcional capaz de:

1. Receber imagens de uma câmera PS3 Eye.
2. Detectar pessoas e elementos de segurança.
3. Avaliar o uso de EPIs.
4. Detectar visualmente fumaça/incêndio.
5. Receber informações de sensores.
6. Tomar decisões de segurança.
7. Comunicar-se com o Raspberry Pi.
8. Acionar dispositivos de alerta.
9. Registrar ocorrências.
10. Apresentar as informações em uma interface de monitoramento.

O principal diferencial do projeto está na **integração de diferentes tecnologias em um único sistema**, combinando visão computacional, inteligência artificial, sensores, sistemas embarcados, comunicação em rede e software de monitoramento.

---

## 11. Observação sobre segurança

O CRTL-Lab é um **protótipo acadêmico** e não deve ser considerado um sistema certificado de segurança ou substituto de equipamentos profissionais de prevenção e combate a incêndio.

Os sensores e modelos de inteligência artificial devem ser utilizados como mecanismos de demonstração e apoio à detecção de situações de risco.

---

## 12. Desenvolvimento inicial do Raspberry

A base do módulo Raspberry já foi iniciada no diretório `raspberry_pi/` com:

- leitura de sensores ambientais;
- gerenciamento de estados do sistema (`NORMAL`, `WARNING`, `ALERT`, `EMERGENCY`);
- controle do buzzer em abstração de hardware;
- suporte a modo mock para testes sem hardware físico;
- preparação para comunicação MQTT com o computador central.

### Execução em modo mock

```bash
cd /home/filipe/Projects/CTRL-Lab
python3 raspberry_pi/main.py --mock --cycles 2
```

Esse comando valida a lógica do sistema e permite verificar a transição entre estados sem necessidade do Raspberry Pi real.

### Executar o dashboard web

Execute o dashboard no computador conectado à rede do Raspberry Pi e ao broker MQTT. Configure um token para proteger os comandos remotos:

```powershell
pip install -r requirements.txt
$env:CTRL_LAB_DASHBOARD_TOKEN = "troque-por-um-token-com-16-caracteres-ou-mais"
python -m central.dashboard --host 0.0.0.0 --port 8000 --broker <IP_DO_RASPBERRY>
```

Descubra o IP do computador que está hospedando o dashboard e acesse `http://<IP_DO_COMPUTADOR>:8000` em um navegador da mesma rede. Digite na página o mesmo token configurado no servidor. O serviço central também registra eventos em `ctrlab_events.db`; use `--db` para alterar o arquivo.

O dashboard atualiza os dados periodicamente pelo MQTT e mostra o estado do sistema, leituras ambientais, os dois modelos, os eventos recentes e a pré-visualização ao vivo da PS3 Eye. O vídeo é capturado uma única vez no Raspberry e entregue como MJPEG de baixa taxa; o dashboard faz o proxy do stream para o navegador. O botão de acesso só envia o comando; a confirmação visual depende do próximo status publicado pelo Raspberry Pi.

Use apenas em uma rede confiável: o HTTP local não é criptografado, portanto não exponha a porta do dashboard nem o broker diretamente à Internet.

### Execução da visão no Raspberry Pi

Conecte a PS3 Eye ao Raspberry Pi e confirme o índice de dispositivo (padrão `0`). Configure um broker MQTT no Pi (por exemplo, Mosquitto) e copie os modelos ONNX para o Raspberry.

#### Preparar o Raspberry Pi OS Lite 64-bit

Para fazer a sincronização do código, instalação das dependências e inicialização automática do runtime com dashboard no Windows, use o [script de início automatizado](./start-ctrlab.ps1) conforme o [guia passo a passo](./docs/GUIA_EXECUCAO.md#início-automatizado-no-windows). Para uma conexão direta por cabo Ethernet sem alterar a rota de Internet, use [start-ctrlab-ethernet.ps1](./start-ctrlab-ethernet.ps1) após configurar os endereços estáticos sem gateway/DNS. O modo padrão é pré-visualização sem IA; modelos ONNX não são instalados pelo script.

Para uma visão consolidada de escopo, arquitetura, sensores, estados, bibliotecas, modelo treinado e roteiro de demonstração, consulte [Apresentação do projeto](./docs/APRESENTACAO_PROJETO.md).

Confirme que o sistema é 64-bit e registre a versão do Python antes de instalar dependências:

```bash
uname -m
python3 --version
cat /etc/os-release
```

Em uma instalação `aarch64`, instale as ferramentas de ambiente virtual e crie o ambiente no diretório do projeto:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-rpi.gpio mosquitto mosquitto-clients
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install adafruit-circuitpython-dht
```

Instale também a biblioteca de sistema `libgpiod` correspondente à versão do Raspberry Pi OS (por exemplo, `libgpiod2` no Bookworm ou `libgpiod3` no Trixie), caso exigida pelo pacote do DHT22.

O ambiente virtual usa pacotes do sistema para permitir o acesso à biblioteca GPIO instalada pelo Raspberry Pi OS. O controle físico requer uma implementação compatível com `RPi.GPIO` para o modelo do Raspberry Pi e a versão do sistema. Se a biblioteca não estiver disponível, o programa registra um aviso e usa GPIO simulado; não considere isso uma atuação física. Confirme a inicialização do GPIO antes dos testes.

O `adafruit-circuitpython-dht` habilita o DHT22 avulso; instale a versão de `libgpiod` compatível com a versão do sistema quando exigida pelo driver. Olhando a grade do DHT22 de frente e os pinos para baixo: pino 1 -> 3,3 V; pino 2 -> GPIO17 (BCM); pino 3 -> sem conexão; pino 4 -> GND. Use um pull-up de aproximadamente 4,7 kΩ entre DATA e 3,3 V. A documentação do driver alerta que o suporte pode variar em Linux 64-bit, então esta leitura precisa ser confirmada no hardware real.

O MQ-2 usa apenas a saída digital DO no GPIO5 (BCM), não mede ppm; confirme se DO é ativo em LOW ou HIGH e use adaptação de nível se a saída ultrapassar 3,3 V. O botão de emergência com trava mecânica fica entre GPIO6 (BCM) e GND; após destravá-lo mecanicamente, pressione o botão de reset no GPIO13. Com um modelo visual configurado, o reset reinicia a visão e aguarda uma inferência válida; se somente pessoa/jaleco estiver configurado, isso não confirma ausência visual de fogo/fumaça. A solicitação de reset é mantida enquanto a visão executa essa verificação, mesmo se o botão for solto. Sem modelo visual, só é possível validar os sensores conectados.

Esta parada é implementada por software e não substitui uma parada de emergência elétrica/certificada: não interrompe a alimentação do Raspberry Pi nem oferece isolamento de potência dos equipamentos.

Nos próximos acessos, ative o ambiente criado:

```bash
source .venv/bin/activate
```

Antes de enviar o projeto, valide o loop simulado sem periféricos:

```bash
python -m raspberry_pi.main --mock --cycles 2
```

Esse comando não valida GPIO, DHT22, câmera ou MQTT real. Os arquivos de modelos ONNX não estão incluídos no repositório; a inferência só poderá ser testada após fornecer modelos treinados compatíveis com as classes configuradas.

Para validar a PS3 Eye antes de obter os modelos, rode um teste de captura independente:

```bash
python -m raspberry_pi.main --camera-test --camera-device 0 --camera-test-frames 30
```

O comando informa quantos frames foram capturados, FPS e resolução, e encerra sem iniciar GPIO/MQTT. Para testar o broker instalado no Pi, inicie o serviço (`sudo systemctl enable --now mosquitto`) e valide localmente com `mosquitto_pub`/`mosquitto_sub`; acesso do dashboard pela rede exige configuração adicional do broker e não deve ser aberto sem autenticação.

Use um segredo de pelo menos 16 caracteres para proteger o stream. Para visualizar a câmera sem IA, inicie o runtime no Pi com `--camera-stream-token` e sem modelos; a câmera transmite vídeo, mas não analisa fogo, fumaça ou jaleco. Esse modo solicita 640x480 a até 24 FPS e captura/codifica de forma síncrona no loop cooperativo. Para inferência de pessoa/jaleco, forneça `--access-model`; com esse modelo isolado, a captura/inferência roda pelo serviço de visão e o modelo começa habilitado. O loop de controle roda a 48 Hz; o DHT22 é consultado a cada 5 s por padrão (mínimo efetivo: 2 s) e o log/status MQTT é atualizado a cada segundo. A última leitura válida do DHT22 é mantida por até 12 s; depois disso, temperatura e umidade aparecem como indisponíveis, com a idade da leitura no campo `dht_age_seconds`. MQ-2 e botões continuam sendo verificados a 48 Hz. O intervalo maior reduz as leituras do DHT22, mas não reduz diretamente o trabalho da câmera. Isso não garante temporização de tempo real nem elimina possíveis problemas elétricos, de USB ou do sistema operacional. Durante uma emergência, a câmera/visão para e recomeça após o reset, conforme os sinais disponíveis e os modelos configurados.

```bash
export CTRL_LAB_CAMERA_TOKEN="use-o-mesmo-token-configurado-no-dashboard"
python3 -m raspberry_pi.main \
  --broker localhost \
  --camera-device 0 \
  --access-model models/ctrlab-access.onnx \
  --access-classes person,lab_coat \
  --camera-stream-token "$CTRL_LAB_CAMERA_TOKEN" \
  --camera-stream-host 127.0.0.1 \
  --image-size 320 \
  --inference-interval 1 \
  --access-vote-window 5
```

O acesso publica a classe vencedora por pessoa ao final de cada janela de 5 segundos; as caixas são associadas entre inferências por sobreposição. Durante a primeira janela, os rótulos ficam como `ANALISANDO`. Use `--access-vote-window 0` para desativar a votação temporal.

Para executar também o detector visual opcional de fogo/fumaça, acrescente `--safety-model models/ctrlab-safety.onnx --safety-classes smoke,fire`. O modelo de pessoa/jaleco começa habilitado quando é o único modelo configurado; com o modelo de segurança adicional, o acesso começa desabilitado.

Para pré-visualização sem inferência, use:

```bash
export CTRL_LAB_CAMERA_TOKEN="use-um-segredo-com-16-caracteres-ou-mais"
python3 -m raspberry_pi.main --broker localhost --camera-device 0 --camera-stream-token "$CTRL_LAB_CAMERA_TOKEN" --camera-stream-host 127.0.0.1
```

No PC, mantenha um segundo túnel SSH ativo para o vídeo:

```powershell
ssh -N -L 8081:127.0.0.1:8081 <usuario>@<IP_DO_RASPBERRY>
```

Inicie o dashboard com o mesmo token:

```powershell
python -m central.dashboard --host 127.0.0.1 --port 8000 --broker 127.0.0.1 --mqtt-port 1884 --control-token "<TOKEN_DO_DASHBOARD>" --camera-stream-token "<TOKEN_DA_CAMERA>" --camera-stream-url http://127.0.0.1:8081/video.mjpg
```

Quando um modelo de acesso está configurado, use `CentralMQTTListener.set_access_model_enabled(True)` (ou publique o payload diretamente no tópico `ctrlab/central/commands`) para controlá-lo:

```json
{"command":"set_access_model","enabled":true}
```

Use `enabled: false` para desabilitar o modelo de acesso. O serviço publica `vision.access.enabled` junto aos resultados no tópico `ctrlab/raspberry/status`. O modelo visual de segurança, quando configurado, não possui comando de desligamento.

Cada modelo deve ser YOLOv8 em ONNX com saída sem NMS no formato `[1, 4 + número_de_classes, candidatos]`. Os nomes e a ordem de cada argumento `--*-classes` precisam corresponder exatamente às classes usadas no treinamento. Um modelo COCO genérico não reconhece automaticamente jaleco; use um detector treinado para essa classe. Para exportar, em uma máquina de desenvolvimento com Ultralytics instalado:

```bash
yolo export model=best.pt format=onnx imgsz=320
```

O Pi não precisa instalar PyTorch ou Ultralytics para executar o modelo. Estados e detecções são publicados no tópico `ctrlab/raspberry/status`; o dashboard os consome para apresentar a telemetria e o histórico sem executar inferência.

Com `CTRL_LAB_CAMERA_TOKEN` configurado, o Raspberry disponibiliza o stream MJPEG protegido em `http://<IP_DO_RASPBERRY>:8081/video.mjpg`. No uso por túnel SSH, mantenha o servidor vinculado a `127.0.0.1` no Pi e crie também o encaminhamento local da porta 8081 (`ssh -N -L 8081:127.0.0.1:8081 <usuario>@<IP_DO_RASPBERRY>`). Inicie o dashboard com o mesmo token em `--camera-stream-token` e `--camera-stream-url http://127.0.0.1:8081/video.mjpg`. Sem o token, a pré-visualização não é iniciada.

---

## 13. Captura da câmera

O projeto usa uma única câmera USB PS3 Eye, adquirida com OpenCV por [app/cameras/entry_camera.py](app/cameras/entry_camera.py). A abstração genérica também aceita outras fontes, mas o runtime do Raspberry configura apenas um dispositivo local USB:

- índice de dispositivo local (padrão `0`);
- configuração inicial de largura, altura e FPS;
- leitura de frames com OpenCV.

Exemplo de uso:

```python
from app.cameras.entry_camera import CameraConfig, StreamCamera

camera = StreamCamera(
    CameraConfig(
        name="ps3_eye",
        width=640,
        height=480,
    ),
    fallback_device=0,
)

camera.open()
frame = camera.read_frame()
print(frame is not None)
camera.close()
```

O Raspberry captura um frame por ciclo e o fornece aos dois modelos. A interface futura recebe estados e eventos via MQTT; ela não abre uma segunda fonte de câmera nem executa inferência.
