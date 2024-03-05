from typing import Tuple

from google.api_core import exceptions as gcloud_exceptions
from google.cloud.pubsub_v1 import PublisherClient, SubscriberClient
from google.cloud.pubsub_v1.types import Subscription as PubSubSubscription

from django_q.brokers import Broker
from django_q.conf import Conf


class Pubsub(Broker):
    def __init__(self, list_key: str = None) -> None:
        self.publisher = None
        self.subscriber = None
        super().__init__(list_key)
        self.subscription = self.get_queue()

    def __setstate__(self, state):
        super().__setstate__(state)
        self.subscription = self.get_queue()

    def enqueue(self, task):
        response = self.publisher.publish(self.subscription.topic, task.encode())
        return response.result()

    def dequeue(self):
        if response := self.subscriber.pull(
            subscription=self.subscription.name, max_messages=Conf.BULK,
        ):
            return [
                (
                    pull_response.ack_id,
                    pull_response.message.data.decode()
                    if pull_response.message.data
                    else None,
                )
                for pull_response in response.received_messages
            ]
        return None

    def acknowledge(self, task_id: str):
        return self.delete(task_id)

    def delete(self, task_id: str):
        self.subscriber.acknowledge(
            subscription=self.subscription.name, ack_ids=[task_id],
        )

    def fail(self, task_id: str):
        self.delete(task_id)

    def delete_queue(self):
        self.subscriber.delete_subscription(subscription=self.subscription.name)
        self.publisher.delete_topic(topic=self.subscription.topic)

    def purge_queue(self):
        self.delete_queue()
        self.create_queue()

    def ping(self) -> bool:
        return hasattr(self.subscriber, "_transport")

    def info(self) -> str:
        return "Google Cloud Pub/Sub"

    @staticmethod
    def get_connection(
        list_key: str = None,
    ) -> Tuple[PublisherClient, SubscriberClient]:
        config = Conf.PUBSUB
        if "google_cloud_project" in config:
            config["project"] = config["google_cloud_project"]
            del config["google_cloud_project"]

        if "google_application_credentials" in config:
            del config["google_application_credentials"]
        publisher = PublisherClient()
        subscriber = SubscriberClient()
        return publisher, subscriber

    def get_queue(self) -> PubSubSubscription:
        self.publisher = self.connection[0]
        self.subscriber = self.connection[1]

        config = Conf.PUBSUB

        # Get / Create topic
        topic_name = self.publisher.topic_path(config["project"], self.list_key)
        try:
            topic = self.publisher.get_topic(topic=topic_name)
        except gcloud_exceptions.NotFound:
            topic = self.publisher.create_topic(name=topic_name)

        # Get / Create subscription to topic
        subscription_name = self.subscriber.subscription_path(
            config["project"], self.list_key,
        )
        try:
            subscription = self.subscriber.get_subscription(subscription=subscription_name)
        except gcloud_exceptions.NotFound:
            subscription = self.subscriber.create_subscription(
                name=subscription_name,
                topic=topic.name,
                ack_deadline_seconds=Conf.RETRY,
            )
        return subscription
