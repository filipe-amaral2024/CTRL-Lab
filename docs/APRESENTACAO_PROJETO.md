# CTRL-Lab — Apresentação do projeto

## Resumo

O **CTRL-Lab** é um protótipo acadêmico de monitoramento e apoio à segurança em laboratórios. Ele integra uma câmera USB, inferência de visão computacional, sensores ligados ao Raspberry Pi, comunicação MQTT e um dashboard web.

Na demonstração atual, a visão computacional está focada em verificar **se pessoas estão usando jaleco**. O buzzer físico é reservado ao estado `EMERGENCY`; a detecção de pessoa sem jaleco gera indicação visual e registro/telemetria, sem tocar o buzzer. O sistema não identifica pessoas e não usa reconhecimento facial.

> **Limite de segurança:** é um protótipo educacional. Não substitui alarmes certificados, procedimentos de laboratório, equipamentos de proteção ou uma parada de emergência elétrica.

## O que o projeto contempla

- Captura de uma câmera PS3 Eye USB conectada ao Raspberry Pi.
- Detecção de pessoas com e sem jaleco usando um modelo YOLOv8 convertido para ONNX.
- Sobreposição visual: caixa verde e `COM JALECO`, ou caixa vermelha e `SEM JALECO`.
- Votação temporal por pessoa: acumula previsões por cinco segundos para reduzir mudanças ocasionais de classe; a caixa acompanha a detecção mais recente.
- Pré-visualização MJPEG protegida por token, encaminhada ao notebook por túnel SSH.
- Leitura de temperatura e umidade com DHT22.
- Leitura digital DO do comparador MQ-2, botões de emergência/reset e controle do buzzer por GPIO.
- Estados de sistema, telemetria e comandos pelo protocolo MQTT.
- Dashboard local para câmera, sensores, estado do sistema, eventos e habilitação/desabilitação da análise visual de acesso.
- Histórico local em SQLite.
- Inicializador PowerShell para sincronizar o software, transferir o modelo opcional, preparar o Raspberry Pi e abrir os túneis e o dashboard.

### Fluxo de dados

```text
PS3 Eye ──USB──► Raspberry Pi ──► captura e inferência ONNX/OpenCV
                      │                         │
       DHT22, MQ-2 DO, botões, buzzer            ├──► caixas e estado jaleco
                      │                         │
                      └──── status/comandos MQTT┘
                                  │
                    túneis SSH por Ethernet ou rede
                                  │
                                  ▼
             Notebook: dashboard web + stream MJPEG + SQLite
```

O broker Mosquitto e o runtime ficam no Pi. O dashboard, o histórico SQLite e o navegador ficam no computador. No uso automatizado, MQTT e vídeo trafegam por túneis SSH; o broker e o stream da câmera não precisam ser expostos diretamente à rede.

## Como funciona

### Visão e modelo de jaleco

O modelo local é um **YOLOv8n de detecção**, treinado para duas classes:

1. `person_with_labcoat`
2. `person_without_labcoat`

O modelo foi treinado no Windows com Ultralytics e depois exportado para ONNX com entrada de 320 × 320 pixels. No Raspberry, a inferência é executada pela implementação OpenCV DNN em CPU; **PyTorch, Ultralytics e CUDA não são necessários no Pi**.

Configurações padrão no runtime:

| Parâmetro | Padrão | Significado |
|---|---:|---|
| Entrada ONNX | 320 × 320 | Dimensão quadrada enviada ao modelo. |
| Confiança mínima | 0,25 | Detecções abaixo de 25% são descartadas antes do NMS. Não significa que a classe acima do limite esteja garantida correta. |
| NMS | 0,45 | Supressão de caixas duplicadas sobrepostas. |
| Ciclo de inferência | 1 s | Intervalo mínimo desejado entre inferências; o ciclo real pode ser mais lento que isso. |
| Votação temporal | 5 s | A classe mais frequente para cada pessoa rastreada determina o estado ao fim da janela. |
| Pré-visualização | alvo nominal de 5 FPS com IA | O stream é atualizado independentemente da inferência; a taxa real depende do Pi, da câmera, da codificação e da rede. |

Durante a primeira janela de votação, as pessoas detectadas aparecem como `ANALISANDO`. Depois da votação, a classe vencedora é mostrada no vídeo e usada no estado de acesso. Se não houver uma detecção nova por 1,5 s, a caixa expira para evitar manter uma posição antiga no frame.

O perfil de classes diretas avalia cada pessoa pela classe retornada. O runtime também mantém compatibilidade com modelos que retornem `person` e `lab_coat`, fazendo associação das caixas.

O acesso visual pode ser habilitado/desabilitado no dashboard. O botão de emergência físico e os sensores físicos não dependem dessa opção.

### Sensores e resposta a risco

Pinos configurados no software (numeração BCM):

| Componente | GPIO | Uso |
|---|---:|---|
| DHT22 | 17 | Temperatura e umidade. |
| MQ-2, saída digital DO | 5 | Estado do comparador: detectado/não detectado. |
| Botão de emergência | 6 | Entrada normalmente aberta para GND, com pull-up. |
| Botão de reset | 13 | Entrada normalmente aberta para GND, com pull-up. |
| Buzzer | 23 | Acionado apenas em `EMERGENCY`. |

Limites padrão incluem temperatura de 30 °C e umidade de 70% para `ALERT`. Emergência pode ser iniciada pelo botão de emergência ou pela entrada digital de gás; o código também aceita um sinal de fumaça/incêndio visual se um modelo de segurança compatível for configurado. O MQ-2 conectado como DO **não mede ppm**. Não há atualmente um modelo visual de fumaça/fogo fornecido para a demonstração.

Estados disponíveis:

- `NORMAL`: sinais configurados sem condição de alerta.
- `WARNING`: limiar intermediário de gás analógico, se houver valor analógico disponível; o circuito atual não fornece essa medição.
- `ALERT`: limites ambientais excedidos ou pessoa sem jaleco após a votação. Sem buzzer.
- `EMERGENCY`: condição crítica ou botão de emergência. O estado fica travado até liberar mecanicamente o botão e solicitar reset; o buzzer toca. A câmera/visão é pausada durante a emergência.

A pausa de software não desliga a alimentação do Pi e não é uma parada de emergência certificada.

### Comunicação e interface

- MQTT de status: `ctrlab/raspberry/status`.
- MQTT de comandos: `ctrlab/central/commands`.
- O dashboard permite comandar a análise visual de acesso quando MQTT está conectado e o token de controle é informado.
- O estado e os sensores são atualizados aproximadamente a cada segundo.
- O vídeo usa MJPEG protegido por token e é encaminhado pelo túnel SSH.
- O histórico é armazenado em `ctrlab_events.db`. A implementação atual persiste payloads de status recebidos; o histórico pode conter snapshots normais além de eventos significativos.

## Modelo treinado e resultados

O dataset utilizado é **Lab Coat Detection 3, versão 12**, exportado do Roboflow Universe. A versão local contém as classes `person_with_labcoat` e `person_without_labcoat`; as anotações poligonais foram convertidas em caixas YOLO para o treinamento. O dataset declara licença **CC BY 4.0** e deve ser atribuído em apresentações e redistribuições.

O treino completo foi executado por 100 épocas no Windows com uma NVIDIA RTX 5060. No split `test` (112 imagens), a validação reportou:

| Classe | Precisão | Recall | mAP50 | mAP50–95 |
|---|---:|---:|---:|---:|
| Com jaleco | 0,977 | 0,944 | 0,960 | 0,952 |
| Sem jaleco | 0,995 | 0,938 | 0,983 | 0,921 |
| Geral | 0,986 | 0,941 | 0,971 | 0,937 |

Foi feita também uma inferência de verificação em imagem do teste usando o detector OpenCV ONNX do próprio projeto. Esses resultados são promissores para o dataset, mas **não garantem a mesma qualidade** com a PS3 Eye, iluminação, distância e ambiente reais do laboratório. A votação temporal suaviza resultados instáveis; não corrige erros persistentes do modelo.

### Arquivos do modelo

Na máquina de treinamento, os arquivos ficam em:

```text
runs/detect/labcoat-v12-py314/weights/best.pt
runs/detect/labcoat-v12-py314/weights/best.onnx
```

O arquivo `.onnx` é o usado na inferência no Pi. Os resultados de treino/modelo ficam localmente e são ignorados pelo Git, portanto **não são incluídos automaticamente ao clonar o repositório**. O inicializador Ethernet copia o modelo informado no parâmetro `-AccessModel`.

### Atribuição sugerida do dataset

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
  note = {Versão 12; licença CC BY 4.0}
}
```

## Bibliotecas e tecnologias

### Execução do projeto

| Biblioteca/tecnologia | Onde é usada | Funcionalidade |
|---|---|---|
| Python 3 | Runtime, dashboard e ferramentas | Linguagem da aplicação. No Pi, o inicializador configura o ambiente virtual e as dependências. |
| OpenCV (`opencv-python-headless`) | Pi e computador | Captura USB, redimensionamento/pré-processamento, JPEG/MJPEG e inferência ONNX por DNN. |
| NumPy | Dependência do OpenCV | Representação e operações sobre matrizes de imagem e tensores. |
| Paho MQTT (`paho-mqtt`) | Pi e computador | Publicação/recepção de status e comandos MQTT. |
| Adafruit CircuitPython DHT (`adafruit-circuitpython-dht`) | Opcional no Pi | Leitura do sensor DHT22; não é necessário para executar o modo sem DHT22. |
| RPi.GPIO / `python3-rpi-lgpio` | Raspberry Pi | Acesso a GPIO em versões compatíveis do Raspberry Pi OS para sensores, botões e buzzer. |
| `gpiod` e `libgpiod` | Raspberry Pi | Suporte necessário ao caminho de leitura de sensores GPIO no ambiente documentado. |
| Mosquitto | Raspberry Pi | Broker MQTT local que conecta o runtime à central. |
| SQLite (`sqlite3`, biblioteca padrão Python) | Computador | Persistência local de status/eventos apresentada no dashboard. |
| `http.server`, `threading`, `argparse` (biblioteca padrão) | Pi e computador | Servidores HTTP simples para dashboard/stream, tarefas de captura e configuração CLI. |
| OpenSSH (`ssh`, `scp`) | Windows | Sincronização remota, inicialização, encaminhamento de portas e transporte do stream sem expor serviços do Pi. |

`requirements.txt` contém dependências Python da aplicação (`paho-mqtt` e `opencv-python-headless`); o inicializador configura também os pacotes específicos do Raspberry Pi.

### Treinamento e exportação — computador de desenvolvimento

| Biblioteca/ferramenta | Funcionalidade |
|---|---|
| Ultralytics | Treinamento/avaliação YOLO, predição em imagens e exportação do modelo. |
| PyTorch + torchvision | Framework de treinamento e operações de visão. Para a GPU usada no treino foi instalada a distribuição CUDA 13.0. |
| CUDA + driver NVIDIA | Acelera o treinamento na GPU compatível. Não é usado pelo runtime ONNX/OpenCV em CPU no Raspberry. |
| ONNX | Formato de intercâmbio exportado para executar o detector no runtime do projeto. |
| Conversor `tools/prepare_labcoat_dataset.py` | Transforma os polígonos do export Roboflow em caixas YOLO e gera estrutura de treino/validação/teste sem alterar os originais. |

Ambiente de treino validado nesta máquina: Python 3.14.5, Ultralytics 8.4.210, PyTorch 2.14.1+cu130, torchvision 0.29.1+cu130 e RTX 5060. As versões de CUDA para treinamento não devem ser instaladas no Raspberry para inferência.

### Modelos de visão

| Modelo | Estado | Função |
|---|---|---|
| YOLOv8n treinado para jaleco | Treinado, avaliado no split de teste e exportado para ONNX | Localiza pessoas e classifica `person_with_labcoat` ou `person_without_labcoat`. É o modelo da demonstração. |
| YOLOv8 ONNX para fumaça/fogo | Opcional; pesos compatíveis ainda precisam ser fornecidos/validados | Infraestrutura aceita classes `smoke,fire`; thresholds de classificação atuais são 0,45 para fumaça e 0,35 para fogo. Não confundir infraestrutura com modelo treinado disponível. |
| Perfil legado `person,lab_coat` | Compatibilidade de runtime | Associa caixas da pessoa e do jaleco. Não é o modelo treinado para esta demonstração. |

## Como executar a demonstração

### Requisitos

- Windows com PowerShell e OpenSSH Client (`ssh` e `scp`).
- Este repositório no computador.
- Raspberry Pi com Raspberry Pi OS Lite 64-bit, SSH ativo e conta usada no script (padrão `ctrl-lab`).
- PS3 Eye conectada por USB ao Pi.
- Rede alcançável por Wi-Fi/Ethernet, ou cabo Ethernet direto configurado conforme abaixo.
- Para sensores físicos: componentes, fiação segura e dependências no Pi.

### Recomendado: notebook ligado diretamente ao Pi por Ethernet

Use um endereço estático local sem gateway/DNS no cabo, deixando a internet no Wi-Fi:

- Ethernet do notebook: `192.168.50.1`, máscara `/24` (`255.255.255.0`), gateway e DNS vazios.
- Ethernet do Pi: `192.168.50.2/24`, sem gateway.

No Raspberry Pi OS com NetworkManager, confirme o perfil Ethernet com `nmcli connection show`; em seguida configure o perfil correto (o exemplo usa `Wired connection 1`):

```bash
sudo nmcli connection modify "Wired connection 1" \
  ipv4.method manual \
  ipv4.addresses 192.168.50.2/24 \
  ipv4.gateway "" \
  ipv4.dns "" \
  ipv4.never-default yes
sudo nmcli connection up "Wired connection 1"
```

No Windows, abra **Configurações → Rede e Internet → Ethernet → (adaptador ligado ao Pi) → Atribuição de IP → Editar → Manual → IPv4**. Defina `192.168.50.1` e prefixo `24`; deixe gateway e DNS vazios. Não altere a interface Wi-Fi.

Teste a conexão no PowerShell:

```powershell
ping 192.168.50.2
Test-NetConnection 192.168.50.2 -Port 22
```

### Iniciar runtime, dashboard e modelo

No PowerShell, na raiz do repositório:

```powershell
.\start-ctrlab-ethernet.ps1 `
    -EthernetInterfaceAlias "Ethernet 2" `
    -AccessModel .\runs\detect\labcoat-v12-py314\weights\best.onnx `
    -AccessClasses "person_with_labcoat,person_without_labcoat"
```

Substitua `Ethernet 2` pelo nome real da interface em `Get-NetAdapter`. O script de Ethernet verifica o IP local, a ausência de rota padrão e o SSH ao Pi, sem modificar endereço IP, Wi-Fi, gateway, DNS ou rotas. Depois chama o inicializador CTRL-Lab, que sincroniza o código, copia o ONNX, verifica/instala dependências, inicia Mosquitto/runtime, cria os túneis e abre o dashboard no navegador.

Se estiver usando uma rede existente em vez do cabo direto:

```powershell
.\start-ctrlab.ps1 `
    -RaspberryHost 192.168.1.50 `
    -AccessModel .\runs\detect\labcoat-v12-py314\weights\best.onnx `
    -AccessClasses "person_with_labcoat,person_without_labcoat"
```

O endereço de exemplo deve ser trocado pelo IP real do Raspberry. Para apenas testar câmera/sensores sem inferência, omita `-AccessModel`. Sem esse argumento, o vídeo é pré-visualização, não uma detecção de jaleco.

Na primeira conexão, o script pode solicitar a senha SSH para registrar uma chave de acesso. Se for necessário instalar pacotes de sistema, pode solicitar também a senha `sudo`. Os tokens de controle/câmera são gerados para a sessão; informe no dashboard o token de controle apresentado no terminal. Mantenha abertas as janelas do túnel e do dashboard enquanto estiver demonstrando.

### Sequência sugerida de demonstração

1. Mostrar a topologia: câmera e sensores no Pi, interface e armazenamento no notebook.
2. Mostrar o vídeo ao vivo e aguardar a primeira janela de votação; rótulos aparecem como `ANALISANDO`.
3. Demonstrar uma pessoa com jaleco (caixa verde) e sem jaleco (caixa vermelha).
4. Explicar que as previsões são agregadas por pessoa em janelas de cinco segundos, evitando que uma única classificação transitória altere o resultado.
5. Demonstrar o dashboard e a telemetria; se montados e validados, mostrar leituras físicas e botões.
6. Explicar que pessoa sem jaleco gera alerta visual, enquanto o buzzer está reservado a `EMERGENCY`.
7. Se for demonstrar emergência/reset, fazê-lo de maneira controlada e sem risco real; validar que a emergência física está liberada e que o reset funciona antes de iniciar.

## Montagem e cuidados elétricos

- Desligue o Pi antes de alterar a fiação; conecte GND comum.
- DHT22: DATA → GPIO17, VCC conforme o módulo (normalmente 3,3 V), GND → GND. Para sensor sem módulo, pull-up de cerca de 4,7 kΩ entre DATA e 3,3 V.
- MQ-2: apenas DO → GPIO5 no software atual. Verifique a tensão de saída; se puder chegar a 5 V, use divisor/conversor de nível para proteger o GPIO de 3,3 V. Não conecte ao GPIO antes de confirmar a tensão.
- Botões normalmente abertos: GPIO6 e GPIO13 respectivamente para GND, sem aplicar 3,3 V/5 V aos pinos.
- Buzzer: GPIO23; use driver/transistor se a corrente exceder o permitido pelo GPIO.
- Consulte o [guia de materiais e montagem](./MATERIAIS_E_MONTAGEM.md) antes de energizar o circuito.

## O que foi validado e o que falta

### Verificado

- Treino de 100 épocas e validação no split de teste do dataset local.
- Exportação ONNX em 320 × 320.
- Carregamento e inferência pontual pelo detector OpenCV do projeto.
- Suíte automatizada local (100 testes passaram na última execução global registrada).
- Sincronização e acesso por cabo direto testados pelo usuário; a conexão foi relatada como estável.
- Ajustes de buffer da câmera para reduzir atraso estão implementados; o backend pode não aceitar o buffer de um frame.

### Ainda depende de ensaio na montagem final

- Desempenho real do modelo no Raspberry: tempo de inferência, CPU, temperatura e cadência efetiva.
- Estabilidade de vídeo com câmera, modelo, dashboard e sensores operando juntos por tempo prolongado.
- Qualidade da detecção na câmera e iluminação do laboratório, com distâncias, roupas e pessoas não vistas no treino.
- Leituras elétricas e resposta de cada sensor/atuador na montagem final.
- Verificação que o GPIO real está ativo e não caiu em fallback mock.
- Critérios de aceitação para falsos positivos/falsos negativos. O protótipo não é dispositivo de segurança certificado.

## Referências do projeto

- [Funcionamento atual e detalhes técnicos](./FUNCIONAMENTO_ATUAL.md)
- [Guia passo a passo de execução](./GUIA_EXECUCAO.md)
- [Materiais e montagem](./MATERIAIS_E_MONTAGEM.md)
- [Pendências de integração e ensaios](./PENDENCIAS_CONCLUSAO.md)
- [Dataset Lab Coat Detection 3 — Roboflow Universe](https://universe.roboflow.com/lab-coat-detection/lab-coat-detection-3/dataset/12)
- [Ultralytics](https://docs.ultralytics.com/)
- [OpenCV](https://opencv.org/)
