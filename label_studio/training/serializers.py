from rest_framework import serializers


class TrainRequestSerializer(serializers.Serializer):
    config_name = serializers.CharField(required=True)
    epochs = serializers.IntegerField(required=False)
    batch = serializers.IntegerField(required=False)
    patience = serializers.IntegerField(required=False)
    imgsz = serializers.IntegerField(required=False)
    device = serializers.CharField(required=False)


class TrainStatusSerializer(serializers.Serializer):
    task_id = serializers.CharField()
    config_name = serializers.CharField()
    status = serializers.CharField()
    progress = serializers.IntegerField()
    current_epoch = serializers.IntegerField(required=False)
    total_epochs = serializers.IntegerField(required=False)
    metrics = serializers.JSONField(required=False)
    result = serializers.JSONField(required=False)
    error = serializers.CharField(required=False)
