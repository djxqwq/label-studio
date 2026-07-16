from rest_framework import serializers


class TrainRequestSerializer(serializers.Serializer):
    config_name = serializers.CharField(required=True)
    epochs = serializers.IntegerField(required=False)
    batch = serializers.IntegerField(required=False)
    patience = serializers.IntegerField(required=False)
    imgsz = serializers.IntegerField(required=False)
    device = serializers.CharField(required=False)


class ModelConfigSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    task_type = serializers.ChoiceField(
        choices=[('obb','OBB'),('detect','Detect'),('cls','CLS'),('seg','SEG')],
        default='obb',
        required=False,
    )
    model_yaml = serializers.CharField(default='yolov8x-obb', required=False)
    model_pt = serializers.CharField(default='yolov8x-obb', required=False)
    data_yaml = serializers.CharField(default='', required=False)
    classes = serializers.ListField(child=serializers.CharField())
    epochs = serializers.IntegerField(default=1000, required=False)
    batch = serializers.IntegerField(default=16, required=False)
    patience = serializers.IntegerField(default=200, required=False)
    imgsz = serializers.IntegerField(default=640, required=False)
    device = serializers.CharField(default='0', required=False)
