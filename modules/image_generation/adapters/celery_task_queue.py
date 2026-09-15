"""Adapter de fila: despacha tasks para o Celery (RabbitMQ).

Import LAZY do Celery dentro do metodo — quem sobe apenas a API nao
precisa do worker importado, e testes de unidade nao tocam no broker.
"""

from __future__ import annotations

from uuid import UUID

from modules.image_generation.application.ports.task_queue import TaskQueuePort


class CeleryTaskQueue(TaskQueuePort):
    def enqueue_generation(self, generation_id: UUID, *, priority: bool = False) -> None:
        from workers.celery_app.tasks import process_generation_task

        queue = "generation.priority" if priority else "generation.standard"
        process_generation_task.apply_async(args=[str(generation_id)], queue=queue)
