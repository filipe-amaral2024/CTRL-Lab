# Status do projeto CTRL-Lab

## Resumo

O CTRL-Lab tem uma base de software implementada para runtime no Raspberry Pi, sensores/GPIO, MQTT, dashboard, histórico SQLite, stream MJPEG e inferência OpenCV DNN para ONNX.

**Sem parâmetros, `start-ctrlab.ps1` inicia pré-visualização sem IA.** Com `-AccessModel <arquivo.onnx>`, transfere o modelo ao Pi e pode iniciar a inferência de pessoa/jaleco sem modelo visual de fogo/fumaça. O runtime também aceita opcionalmente o detector visual de segurança. O modelo de jaleco foi treinado, avaliado no split de teste e exportado localmente; os pesos em `runs/` são ignorados pelo Git. Ainda falta validar a qualidade, o desempenho e o circuito na montagem final do Pi.

## Implementado no código

- Runtime Raspberry com leitura de DHT22, leitura digital do comparador DO do MQ-2, botões de emergência/reset e buzzer.
- Máquina de estados `NORMAL`, `WARNING`, `ALERT` e `EMERGENCY`.
- Captura OpenCV de câmera USB e pré-visualização MJPEG protegida por token.
- Inferência focada em pessoa/jaleco por ONNX/OpenCV DNN, aceitando `person,lab_coat` ou `person_with_labcoat,person_without_labcoat`.
- Dataset local de status de jaleco, conversor de polígonos para caixas YOLO e modelo YOLOv8 treinado/exportado para ONNX.
- Detector visual de segurança ONNX opcional; modelo de acesso pode ser controlado por MQTT e pela tecla `A` quando configurado.
- Comunicação MQTT entre Pi e central, dashboard web e armazenamento SQLite.
- Inicializador PowerShell que instala/verifica dependências, sincroniza o código, transfere opcionalmente o modelo pessoa/jaleco, prepara o runtime, estabelece túneis e abre o dashboard.
- Suíte automatizada local; a última execução completa registrada após a votação temporal: 100 testes aprovados.

## Ainda não comprovado/concluído

- Os pesos ONNX não são versionados e precisam estar disponíveis localmente ou ser fornecidos ao inicializador.
- Integração no runtime de quaisquer sensores físicos dedicados de chama/fumaça: atualmente o código configura o MQ-2 apenas pela saída digital DO.
- Teste de ponta a ponta do modelo e sensores na montagem final do Raspberry, incluindo qualidade de inferência e carga de CPU.
- Estabilidade prolongada da câmera e medição de FPS/resolução efetivos no runtime completo; o buffer de captura foi limitado a um frame quando o backend suporta essa opção.
- Leitura física correta de sensores e atuadores, GPIO real sem fallback para mock e validação elétrica.
- Precisão, latência e carga de CPU/memória dos modelos no Raspberry.
- Validação real de MQTT, dashboard, comandos e histórico durante uma sessão completa.
- Ajuste do armazenamento para separar telemetria periódica de eventos significativos.
- Ensaio e critérios de aceite para a apresentação.

## Documentação de referência

- [Funcionamento atual](./FUNCIONAMENTO_ATUAL.md)
- [Apresentação do projeto](./APRESENTACAO_PROJETO.md)
- [Pendências para concluir](./PENDENCIAS_CONCLUSAO.md)
- [Guia passo a passo](./GUIA_EXECUCAO.md)
- [Materiais e montagem](./MATERIAIS_E_MONTAGEM.md)
- [Plano de desenvolvimento original](../PLANO_DESENVOLVIMENTO.md)

> O projeto é um protótipo acadêmico e não substitui sistemas ou dispositivos certificados de segurança.
