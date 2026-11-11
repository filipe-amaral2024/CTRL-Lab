# CTRL-Lab: funcionamento atual

Este documento descreve o comportamento encontrado no código do repositório, distinguindo o que está implementado do que ainda depende de modelos, hardware e validação no Raspberry Pi. A arquitetura pretendida está descrita no [README principal](../README.md); este documento é a referência para o comportamento atual do runtime.

> **Resumo importante:** sem parâmetros adicionais, `start-ctrlab.ps1` inicia o modo de pré-visualização sem IA. Para a demonstração de jaleco, passe um ONNX por `-AccessModel`; o script copia o modelo ao Pi e inicia a análise de pessoa/jaleco sem exigir modelo visual de fogo/fumaça. O repositório não contém pesos treinados. Os sensores físicos existentes continuam trabalhando independentemente dos modelos visuais.

## 1. Visão do sistema

O Raspberry Pi é responsável por adquirir dados dos periféricos, executar a lógica de estado, publicar telemetria MQTT e, quando configurado, capturar vídeo e executar inferência. O computador abre o dashboard e recebe o vídeo por um túnel SSH.

```text
PS3 Eye (USB) ──► Raspberry Pi ──► MJPEG protegido ──► túnel SSH ──► dashboard
                       │
                       ├── captura local OpenCV (índice configurável)
                       ├── DHT22, MQ-2 digital, botões e buzzer via GPIO
                       ├── lógica de estados e emergência
                       ├── modelos ONNX opcionais (OpenCV DNN / CPU)
                       └── MQTT ──► Mosquitto no Pi ──► túnel SSH ──► dashboard
                                                               │
                                                               └── SQLite de eventos
```

O endereço da câmera no dashboard não representa uma câmera conectada ao PC: o dispositivo USB pertence ao Raspberry. O navegador recebe uma sequência de imagens JPEG produzidas pelo runtime no Pi.

## 2. Modos disponíveis

| Modo | Como é iniciado | O que faz | Estado no script automatizado |
|---|---|---|---|
| Simulação | `python -m raspberry_pi.main --mock` | Usa dados simulados e não exige sensores reais. Não comprova GPIO, DHT22, câmera ou rede física. | Não é o modo padrão do script. |
| Teste de câmera | `python -m raspberry_pi.main --camera-test --camera-device 0 --camera-test-frames 30` | Abre a câmera, captura uma quantidade finita de frames, informa resolução observada e FPS medido e encerra sem iniciar o runtime de sensores/MQTT. | Deve ser executado separadamente para diagnóstico. |
| Pré-visualização sem IA | Runtime com `--camera-stream-token`, sem `--safety-model` | Captura a câmera e serve MJPEG protegido; não classifica fogo, fumaça ou EPI. | **Modo iniciado por `start-ctrlab.ps1`.** |
| Inferência visual | Runtime com `--access-model` e/ou `--safety-model` | Pessoa/jaleco pode rodar sozinho; detector visual de fogo/fumaça é opcional. | Implementado no código; depende de pesos ONNX externos. |

Sem `-AccessModel`, o inicializador não envia pesos e não executa inferência visual. Com `-AccessModel <arquivo.onnx>`, ele valida e copia o modelo para `~/CTRL-Lab/models/ctrlab-access.onnx`, iniciando a verificação de jaleco. A mensagem “dashboard funcionando” ou a imagem ao vivo, por si só, não significa que exista inferência visual.

## 3. Inicialização automatizada no Windows

Na raiz do repositório, o fluxo é:

```powershell
.\start-ctrlab.ps1
```

O script usa os parâmetros de host e usuário SSH configurados no arquivo (atualmente, `ctrl-lab` e `192.168.15.75`, salvo substituição pelo parâmetro `-RaspberryHost`). Em termos gerais, ele:

1. Confere as ferramentas Python, OpenSSH e as portas locais do dashboard e dos túneis.
2. Instala as dependências Python do computador em `.venv`.
3. Usa ou cria uma chave SSH Ed25519 local e, no primeiro pareamento, instala a chave pública no Pi depois da autenticação SSH.
4. Copia os módulos necessários para `~/CTRL-Lab` no Pi.
5. Instala/verifica dependências de sistema e Python no Raspberry, habilita o Mosquitto e prepara o ambiente virtual.
6. Substitui com segurança um runtime anterior do projeto encontrado no mesmo diretório e inicia o runtime sem IA, registrando PID e log em `~/CTRL-Lab/`.
7. Abre um túnel para MQTT (porta local 1884 para a porta 1883 do Pi) e outro para o vídeo (porta local 8081 para a porta 8081 do Pi).
8. Inicia o dashboard local em `http://127.0.0.1:8000`, consulta a disponibilidade dos serviços e abre o navegador.

O script gera tokens para a execução e mostra o token de controle no terminal. O token de câmera é passado ao runtime e ao dashboard, sem ser salvo em arquivo. A chave privada SSH sem senha depende da proteção da conta Windows. A senha de `sudo` do Raspberry, se solicitada para instalar pacotes, é independente da senha SSH.

O túnel deve permanecer aberto durante o uso do dashboard. O runtime no Pi pode continuar ativo depois que as janelas do PC forem fechadas; encerre-o de forma controlada usando o comando apresentado pelo próprio inicializador ou interrompendo a sessão correspondente.

### Rede

O IP usado no parâmetro deve ser alcançável pelo PC e ter SSH ativo na porta 22. Uma mensagem `Connection timed out` ocorre antes da autenticação por chave: indica IP incorreto, redes diferentes, Raspberry desligado ou rota/porta inacessível, não uma chave SSH inválida. A rede cabeada pode melhorar a estabilidade do transporte de vídeo, mas não acelera a captura USB nem a inferência local.

## 4. Captura e transmissão da câmera

### Pré-visualização sem IA

- A PS3 Eye é aberta pelo OpenCV como câmera local; `--camera-device` seleciona o índice e o padrão é `0`.
- A configuração solicita **640×480**, proporção 4:3 (VGA), e um alvo de **24 FPS**.
- A captura e a codificação JPEG são síncronas no loop cooperativo do runtime. A aplicação tenta capturar quando vence o intervalo de 1/24 s; tempo de leitura, codificação, driver e carga podem reduzir a taxa real e atrasar um tick do loop.
- Um servidor MJPEG no Raspberry publica o JPEG mais recente. No fluxo automatizado, ele fica acessível somente em `127.0.0.1:8081` no Pi; o PC o alcança pelo túnel SSH.
- A interface do dashboard recebe o MJPEG por um endpoint proxy local. A fluidez observada depende também do Pi, da codificação, da rede/túnel, do proxy e do navegador.
- A câmera e a pré-visualização são pausadas durante `EMERGENCY`.

Os 24 FPS são um pedido ao driver, não uma taxa garantida ou uma medição. O teste `--camera-test` mede uma captura isolada e serve para checar o dispositivo; não mede a estabilidade do runtime completo, a transmissão, a inferência ou o DHT22 em conjunto.

### Com IA configurada

O serviço de visão abre uma captura única e compartilha os frames entre os detectores. Com token de pré-visualização habilitado, uma thread de captura mantém o frame mais recente disponível para inferência; a prévia JPEG é atualizada aproximadamente a cada 0,2 s (alvo de 5 FPS). A inferência lê um frame recente, executa o detector de segurança e, se o acesso estiver habilitado, executa também o detector de acesso sobre esse frame.

O intervalo padrão entre ciclos de inferência é **1 segundo** (`--inference-interval`); é um intervalo mínimo entre ciclos, não uma garantia de execução nesse ritmo, pois a inferência pode demorar mais. O stream mantém pré-visualização nominal de 5 FPS sem executar inferência em cada frame. Para pessoa/jaleco, os resultados são agrupados em janelas de votação de **5 segundos** (`--access-vote-window`): as caixas são associadas entre inferências por IoU, cada pessoa recebe sua classe mais frequente ao fim da janela e o estado de acesso só muda nesse fechamento. Durante a primeira janela, a pessoa aparece como `ANALISANDO`; use `--access-vote-window 0` para desativar a estabilização.

Quando executado sozinho, o modelo de pessoa/jaleco começa habilitado; o dashboard ou a tecla `A` pode pausá-lo/reativá-lo. Se segurança e acesso forem configurados juntos, o detector de segurança roda continuamente e o modelo de acesso começa desabilitado. O controle do acesso nunca desliga o detector de segurança.

## 5. Sensores e GPIO

Configuração padrão declarada em `raspberry_pi/config.py`:

| Componente | GPIO BCM | Funcionamento atual |
|---|---:|---|
| DHT22 | 17 | Temperatura/umidade; consultado a cada 5 s por padrão, com mínimo efetivo de 2 s. |
| Saída digital DO do MQ-2 | 5 | Estado digital do comparador. Polaridade padrão ativa em LOW; `--mq2-active-high` inverte. Sinaliza o limiar configurado no módulo; não mede ppm. |
| Botão de emergência | 6 | Entrada com pull-up; pressão é identificada por evento GPIO. |
| Botão de reset | 13 | Entrada com pull-up; pressão é identificada por evento GPIO. |
| Buzzer | 23 | Ligado em `WARNING`/`ALERT`; desligado em `NORMAL` e `EMERGENCY`. |

O loop cooperativo roda a 48 Hz por padrão. O DHT22 é limitado separadamente por seu intervalo; MQ-2 e estados dos botões são atualizados/consultados pelo caminho de hardware do runtime. Uma leitura DHT22 válida é mantida por até 12 s; depois desse prazo, temperatura e umidade ficam indisponíveis (`null` no status), e a idade continua informada em `dht_age_seconds`.

No modo de hardware real, dados indisponíveis não são substituídos por números aleatórios. O DHT22 requer biblioteca, fiação e pull-up adequados. O MQ-2 é apenas uma entrada digital de limiar e não deve ser ligado ao GPIO sem confirmar a tensão de DO e, se necessário, adaptar o nível para 3,3 V. Consulte [Materiais e montagem](./MATERIAIS_E_MONTAGEM.md) antes de energizar o circuito.

Se `RPi.GPIO` não puder ser importado, a abstração GPIO atual pode cair para modo mock e registrar um aviso. Portanto, verificar os logs e comprovar as entradas/saídas no Pi real é obrigatório; a inicialização do processo, sozinha, não prova que o hardware está ativo.

## 6. Estados e resposta a risco

O `AlertManager` combina entradas ambientais e, quando existe inferência, o estado visual. As prioridades são `NORMAL`, `WARNING`, `ALERT` e `EMERGENCY`; o estado de maior prioridade prevalece.

- **WARNING**: limiar intermediário de gás analógico, quando há dado analógico disponível. O hardware atual do MQ-2 só fornece estado digital.
- **ALERT**: temperatura igual/superior a 30 °C ou umidade igual/superior a 70%.
- **EMERGENCY**: botão de emergência, estado digital de gás detectado, fumaça/incêndio reportado ou outra condição classificada como emergência.
- A emergência fica travada até o botão mecânico ser liberado e um reset ser solicitado. Com visão configurada, a câmera/visão volta para confirmar condição segura antes de liberar o estado. Sem visão, o software só pode revalidar entradas disponíveis; não existe confirmação visual.
- Enquanto a emergência está travada, a câmera/visão é pausada e o buzzer permanece acionado. O processo, MQTT e a leitura de sensores/botões permanecem ativos para monitoramento e reset. Nos estados WARNING/ALERT, inclusive alerta de pessoa sem jaleco, o buzzer fica desligado.

Essa lógica é uma resposta de software de protótipo. Não é uma parada de emergência certificada nem substitui alarmes, proteções ou procedimentos de segurança do laboratório.

## 7. MQTT, dashboard e armazenamento

- Broker Mosquitto: instalado/iniciado no Raspberry pelo script, com o runtime publicando localmente no Pi.
- Tópico de status: `ctrlab/raspberry/status`.
- Tópico de alerta: `ctrlab/raspberry/alerts` (definido na configuração; validar publicação efetiva durante integração).
- Tópico de comando: `ctrlab/central/commands`.
- O Raspberry publica o status aproximadamente a cada segundo e ao mudar de estado.
- A mensagem inclui estado, valores ambientais, botões, idade do DHT22 e, quando disponível, detalhes da visão.
- O listener central recebe os status MQTT e o dashboard apresenta conectividade, métricas e eventos recentes. O SQLite padrão é `ctrlab_events.db`.
- O dashboard permite solicitar que o modelo de acesso seja ligado/desligado, usando um token de controle; o token da câmera também protege o MJPEG.
- No fluxo automatizado, o dashboard se vincula a `127.0.0.1`; o acesso é feito localmente no PC. MQTT e vídeo atravessam o túnel SSH.

**Observação sobre o histórico:** o listener persiste cada payload de status recebido chamando `save_payload`; portanto, o SQLite atual pode armazenar snapshots periódicos como eventos, inclusive estados normais. Separar histórico de telemetria de eventos significativos é uma pendência antes de tratar a tela como registro operacional.

## 8. Modelos e inferência

O código executa YOLOv8 exportado para ONNX usando OpenCV DNN no alvo CPU. O detector valida o arquivo, nomes/quantidade de classes e formato esperado da saída.

Valores padrão do CLI:

- Segurança visual (opcional): classes `smoke,fire`; thresholds de classificação em `FireDetector` de 0,45 para fumaça e 0,35 para fogo.
- Pessoa/jaleco: perfil legado `person,lab_coat` ou perfil direto `person_with_labcoat,person_without_labcoat`; somente o status do jaleco é avaliado.
- Entrada do modelo: 320×320 (`--image-size 320`).
- Intervalo entre ciclos: 1 s (`--inference-interval 1`).
- Janela de votação temporal por pessoa: 5 s (`--access-vote-window 5`).
- Limiar de confiança do detector ONNX: 0,25; NMS: 0,45.
- A avaliação do modo de demonstração exige jaleco; outros itens de EPI não são avaliados.

No perfil `person,lab_coat`, o código associa o centro da caixa do jaleco à caixa de uma pessoa. No novo perfil, cada caixa é classificada diretamente como pessoa com ou sem jaleco e qualquer detecção `person_without_labcoat` produz alerta. O perfil direto não depende de associar caixas separadas. Validar as detecções em imagens e no enquadramento real continua necessário. Os thresholds, pesos, compatibilidade de pré-processamento, desempenho e qualidade das decisões ainda precisam ser medidos. **Nenhum peso `.onnx`, `.pt` ou `.tflite` treinado está incluído no repositório.**

O detector visual de fogo/fumaça pode ser adicionado depois ou junto do detector de jaleco. Sua ausência é exibida como não configurada e não desativa os sensores físicos. No código atual, o MQ-2 está configurado como uma entrada digital de gás/limiar; sensores físicos dedicados de chama ou fumaça precisam ter seus pinos e lógica integrados antes de aparecerem como sinais próprios no status.

### Dataset local: Lab Coat Detection 3 v12

O dataset Roboflow foi adicionado localmente em `Lab Coat Detection 3.v12i.yolov8`. O YAML declara as classes `person_with_labcoat` e `person_without_labcoat`, licença CC BY 4.0 e divisões de treino, validação e teste. O `data.yaml` original foi ajustado para apontar para as pastas de imagens existentes dentro do dataset.

As anotações exportadas são segmentações poligonais, enquanto o runtime atual executa detecção de caixas YOLOv8. O utilitário `tools/prepare_labcoat_dataset.py` converte os polígonos em caixas delimitadoras e prepara uma cópia em `training/generated/labcoat-detection`, sem alterar as anotações originais. O modelo foi treinado e avaliado localmente no split de teste; seus arquivos estão em `runs/detect/labcoat-v12-py314/weights/` e são ignorados pelo Git. O runtime e o inicializador aceitam as duas classes de status. **A validação no Raspberry Pi e com imagens reais da PS3 Eye continuam pendentes**; a qualidade das anotações e a capacidade de generalização devem ser verificadas em condições do ambiente de demonstração.

O dataset não é o mesmo que o workflow hospedado `general-segmentation-api` mencionado anteriormente. Ainda não foi confirmado que esse workflow usa esta versão do dataset. A validação local descrita aqui não exige API nem credencial.

Na apresentação e no relatório, cite a origem sob a licença indicada pelo export:

```bibtex
@misc{lab-coat-detection-3-v12,
  title = {Lab Coat Detection 3 Dataset},
  type = {Open Source Dataset},
  author = {Lab Coat Detection},
  howpublished = {\url{https://universe.roboflow.com/lab-coat-detection/lab-coat-detection-3/dataset/12}},
  url = {https://universe.roboflow.com/lab-coat-detection/lab-coat-detection-3/dataset/12},
  journal = {Roboflow Universe},
  publisher = {Roboflow},
  year = {2026},
  note = {Versão 12, exportada em 2026-06-29; licença CC BY 4.0}
}
```

## 9. Testes e limites conhecidos

Os testes automatizados verificam componentes com mocks: sensores, GPIO, MQTT, câmera/stream, lógica de estados, dashboard, eventos, processamento ONNX e conversão do dataset. A suíte completa passou **97 testes** após as alterações para as classes pessoa-com/sem-jaleco.

Esses testes não substituem validação no hardware. Eles não demonstram por si só:

- que o Pi está acessível ou que o script completou o deploy;
- que a PS3 Eye e o driver mantêm 640×480/24 FPS no runtime completo;
- que os sensores físicos estão ligados corretamente e produzem leituras estáveis;
- que o GPIO real está ativo (especialmente se ocorrer fallback para mock);
- que os modelos detectam corretamente os cenários do laboratório;
- que CPU, memória, temperatura e USB são suficientes para inferência contínua;
- que o dashboard e os comandos remotos funcionam com o broker e a rede reais.

## 10. Arquivos centrais

- [Inicializador Windows](../start-ctrlab.ps1)
- [Runtime Raspberry](../raspberry_pi/main.py)
- [Configuração de hardware e limites](../raspberry_pi/config.py)
- [Leitura dos sensores](../raspberry_pi/sensors.py)
- [GPIO](../raspberry_pi/hardware.py)
- [Estados e alertas](../raspberry_pi/alerts.py)
- [Captura e inferência](../raspberry_pi/vision.py)
- [Configuração da câmera](../app/cameras/entry_camera.py)
- [Detector ONNX](../app/vision/yolo_onnx.py)
- [Dashboard central](../central/dashboard.py)
- [Listener MQTT](../central/mqtt_listener.py)
- [Persistência SQLite](../central/events.py)
- [Guia de execução](./GUIA_EXECUCAO.md)
- [Pendências para concluir](./PENDENCIAS_CONCLUSAO.md)
