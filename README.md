# CRTL-Lab — Controle de Acesso e Segurança para Laboratórios

## 1. Visão geral

O **CRTL-Lab** é um sistema de controle de acesso e monitoramento de segurança para laboratórios, desenvolvido como projeto acadêmico para a feira de Computação.

A proposta combina **visão computacional, inteligência artificial, sensores ambientais e automação** para auxiliar na prevenção e identificação de situações de risco em um laboratório.

O sistema utiliza uma única câmera **PS3 Eye** conectada por USB ao **Raspberry Pi 3B+**. A câmera fornece frames compartilhados para dois modelos de visão: o modelo de segurança permanece ativo e o modelo de acesso pode ser ligado/desligado durante a execução.

Os modelos são executados diretamente pelo Raspberry Pi. A captura não depende de stream IP de celular, evitando a latência e os travamentos observados. O computador recebe estado e eventos via MQTT; o dashboard web permite acompanhar sensores, riscos e histórico e controlar remotamente o modelo de acesso pela rede local.

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
- Acionar LEDs, buzzer ou sirene em situações de alerta.
- Registrar eventos e ocorrências.
- Disponibilizar uma interface para acompanhamento do sistema.
- Demonstrar a integração entre inteligência artificial, software, sensores e sistemas embarcados.

---

## 3. Funcionalidades propostas

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

Os itens inicialmente considerados são:

- Jaleco de manga comprida.
- Óculos de proteção.
- Calçado fechado.
- Cabelo devidamente preso, quando aplicável.

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

Ao desabilitar o modelo de acesso, a câmera e o modelo de segurança continuam funcionando.

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
- Acender LEDs.
- Acionar um buzzer.
- Acionar uma sirene.
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
- Controle de LEDs.
- Controle de buzzer/sirene.
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
- LEDs
- Resistores
- Buzzer
- Sirene, se disponível
- Botão de emergência/reset
- Fonte e componentes de prototipagem

---

## 6. Inteligência artificial

O projeto não pretende desenvolver uma rede neural do zero. O Raspberry executa dois modelos YOLOv8 ONNX pequenos pelo OpenCV DNN, em CPU, sobre o mesmo frame da PS3 Eye. O modelo de segurança roda continuamente; o modelo de acesso é opcional e inicia desabilitado. Seu ONNX só é carregado quando habilitado e liberado da memória ao desativá-lo.

Serão utilizadas bibliotecas e modelos existentes, principalmente:

- **OpenCV DNN** para inferência local com o modelo YOLOv8 ONNX.
- **Ultralytics**, opcional na máquina de desenvolvimento, para exportar modelos treinados.

Os modelos são arquivos ONNX separados, com lista de classes própria: `smoke,fire` para segurança e `person,lab_coat,safety_glasses,closed_shoes,tied_hair` para acesso/EPI.

O modelo de acesso pode ser ligado/desligado durante a execução pelo atalho `A` no terminal ou pelo dashboard via MQTT. Esse controle nunca desativa a checagem de segurança.

### Possíveis classes do modelo de acesso/EPI

```text
person
lab_coat
safety_glasses
closed_shoes
tied_hair
```

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
- Óculos: SIM
- Calçado fechado: NÃO
- Cabelo preso: SIM

Resultado:
ACESSO NEGADO
Motivo:
Calçado inadequado
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

- Pessoa sem óculos de proteção.
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
| 10:30 | EPI | Pessoa sem óculos | ALERTA |
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
- controle de LEDs e buzzer/sirene em abstração de hardware;
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

Instale as dependências Python em um ambiente virtual no Raspberry:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Use o mesmo segredo de pelo menos 16 caracteres no Raspberry e no computador do dashboard para proteger o stream. Exemplo de execução no Pi com os dois modelos. O modelo de acesso começa desabilitado; pressione `A` no terminal para alterná-lo.

```bash
export CTRL_LAB_CAMERA_TOKEN="use-o-mesmo-token-configurado-no-dashboard"
python3 -m raspberry_pi.main \
  --broker localhost \
  --camera-device 0 \
  --safety-model models/ctrlab-safety.onnx \
  --access-model models/ctrlab-access.onnx \
  --safety-classes smoke,fire \
  --access-classes person,lab_coat,safety_glasses,closed_shoes,tied_hair \
  --image-size 320 \
  --inference-interval 3
```

O serviço pode ser executado apenas com segurança, omitindo `--access-model`. Para controle do dashboard, use `CentralMQTTListener.set_access_model_enabled(True)` (ou publique o payload diretamente no tópico `ctrlab/central/commands`):

```json
{"command":"set_access_model","enabled":true}
```

Use `enabled: false` para desabilitar o modelo de acesso. O serviço publica `vision.access.enabled` junto aos resultados no tópico `ctrlab/raspberry/status`. O modelo de segurança não possui comando de desligamento.

Cada modelo deve ser YOLOv8 em ONNX com saída sem NMS no formato `[1, 4 + número_de_classes, candidatos]`. Os nomes e a ordem de cada argumento `--*-classes` precisam corresponder exatamente às classes usadas no treinamento. Um modelo COCO genérico não reconhece automaticamente jaleco, óculos, calçados, cabelo preso, fumaça ou fogo: use modelos treinados para essas classes. Para exportar, em uma máquina de desenvolvimento com Ultralytics instalado:

```bash
yolo export model=best.pt format=onnx imgsz=320
```

O Pi não precisa instalar PyTorch ou Ultralytics para executar o modelo. Estados e detecções são publicados no tópico `ctrlab/raspberry/status`; o dashboard os consome para apresentar a telemetria e o histórico sem executar inferência.

Com `CTRL_LAB_CAMERA_TOKEN` configurado, o Raspberry disponibiliza o stream MJPEG protegido em `http://<IP_DO_RASPBERRY>:8081/video.mjpg`. O dashboard usa por padrão o host informado em `--broker` para conectar ao stream; ajuste com `--camera-stream-url` se o endereço da câmera for diferente. Libere a porta TCP `8081` entre o computador do dashboard e o Raspberry. Sem o token, a pré-visualização não é iniciada.

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
