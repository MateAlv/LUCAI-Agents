# LUCAI-Agents
Este proyecto tiene como objetivo desarrollar agentes funcionales a los clientes de LUCAI. Tenemos dos focos iniciales sobre los cuales comenzar a planificar una infraestructura de software y decisiones claves de diseño. El primer foco tiene el fin de de abrir un canal de LUCAI capaz de recibir consultas en lenguaje natural y proveer una respuesta de una query especifica en nuestras bases de datos SQL. El segundo enfoque consiste en hacer un newsletter de avances tecnológicos, financieros y académicos particulares a una de nuestras startups clientes.
En principio, es necesario decidir alrededor de qué framework vamos a realizar el desarrollo de los agentes. Por otro lado, es necesario comenzar a pensar y definir qué modelo/s de IA vamos a utilizar en los pasos intermedios y redacción de texto hacia el usuario. 

## Framework
Se están estudiando dos opciones viables:
- LangChain: Es un entorno de desarollo de aplicaciones que hacen uso de LLMs. Útil si se hace uso de tooling, o un entorno con múltiples agentes, integración compleja.
- Python: Usar python "crudo" sin un entorno exterior provee un control total sobre el agente y una menor curva de aprendizaje. A su vez, más adelante se pueden acoplar los desarrollos a un framework específico en caso de desearse. Esto es más útil para realizar pruebas a menor escala y es más fácil de depurar. 


# Bio Watchdog — agente de vigilancia biotech (AR + global)

Qué hace: ingesta noticias (RSS/HTML), papers (arXiv) y registros clínicos (ClinicalTrials), les saca el jugo (resumen, flags, score), filtra ruido automáticamente y genera un newsletter en Markdown seccionado (Tech / Finanzas / Académico). Todo on-prem y en Python puro.

## Flujo:
sources → clean → flags+summary → score → critic → re-score → classify → MMR → markdown

Sources: RSS (Endpoints, Agencia I+D+i), HTML (CONICET con selectores CSS), APIs (arXiv q-bio, ClinicalTrials AR, opcional GDELT).

Normalización: limpieza HTML con trafilatura.

Enriquecido: flags [AR] (Argentina) y [FIN] (ronda/grant), resumen breve.

Ranking: recency half-life + pesos de dominio + boosts (AR/FIN/watchlist) + embeddings (sentence-transformers) con MMR para diversidad.

Crítico: reglas anti-ruido (social, paywall “demote”, textos muy cortos, umbral de score).

Render: Markdown final en output/newsletter_YYYYMMDD.md.
