# Status do projeto CTRL-Lab

## Resumo

O CTRL-Lab tem uma base de software implementada para runtime no Raspberry Pi, sensores/GPIO, MQTT, dashboard, histórico SQLite, stream MJPEG e inferência OpenCV DNN para ONNX.

**O fluxo iniciado atualmente por `start-ctrlab.ps1` é de pré-visualização sem IA.** Ele transmite a PS3 Eye USB, mas não detecta fogo, fumaça ou EPI. A inferência só é executada quando um modelo ONNX é fornecido por argumento; os pesos não estão presentes no repositório. A conclusão funcional depende de testes no Pi real, modelos validados e comprovação do circuito.

## Implementado no código

- Runtime Raspberry com leitura de DHT22, leitura digital do comparador DO do MQ-2, botões de emergência/reset e buzzer.
- Máquina de estados `NORMAL`, `WARNING`, `ALERT` e `EMERGENCY`.
- Captura OpenCV de câmera USB e pré-visualização MJPEG protegida por token.
- Infraestrutura opcional para detectores YOLOv8 ONNX via OpenCV DNN/CPU; modelo de acesso pode ser controlado por MQTT e pela tecla `A` quando configurado.
- Comunicação MQTT entre Pi e central, dashboard web e armazenamento SQLite.
- Inicializador PowerShell que instala/verifica dependências, sincroniza o código, prepara o runtime, estabelece túneis e abre o dashboard.
- Suíte automatizada local; última execução completa reportada: 83 testes aprovados.

## Ainda não comprovado/concluído

- Modelos ONNX treinados, compatíveis e avaliados; nenhum peso foi encontrado no repositório.
- Conexão e deploy de ponta a ponta no Raspberry atualizado. O último erro reportado foi timeout SSH no endereço padrão `192.168.15.75`; confirmar o IP/rede atual.
- Estabilidade da câmera e medição de FPS/resolução efetivos no runtime completo.
- Leitura física correta de sensores e atuadores, GPIO real sem fallback para mock e validação elétrica.
- Precisão, latência e carga de CPU/memória dos modelos no Raspberry.
- Validação real de MQTT, dashboard, comandos e histórico durante uma sessão completa.
- Ajuste do armazenamento para separar telemetria periódica de eventos significativos.
- Ensaio e critérios de aceite para a apresentação.

## Documentação de referência

- [Funcionamento atual](./FUNCIONAMENTO_ATUAL.md)
- [Pendências para concluir](./PENDENCIAS_CONCLUSAO.md)
- [Guia passo a passo](./GUIA_EXECUCAO.md)
- [Materiais e montagem](./MATERIAIS_E_MONTAGEM.md)
- [Plano de desenvolvimento original](../PLANO_DESENVOLVIMENTO.md)

> O projeto é um protótipo acadêmico e não substitui sistemas ou dispositivos certificados de segurança.
