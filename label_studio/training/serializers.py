from rest_framework import serializers


class TrainRequestSerializer(serializers.Serializer):
    config_name = serializers.CharField(required=True)
    project_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        required=True,
        help_text='一个或多个项目 ID，合并为训练集',
    )
    epochs = serializers.IntegerField(required=False, min_value=1)
    batch = serializers.IntegerField(required=False, min_value=1)
    patience = serializers.IntegerField(required=False, min_value=1)
    imgsz = serializers.IntegerField(required=False, min_value=32)
    device = serializers.CharField(required=False, allow_blank=True)


class ModelConfigSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    task_type = serializers.ChoiceField(
        choices=[('obb', 'OBB'), ('detect', 'Detect'), ('cls', 'CLS'), ('seg', 'SEG')],
        default='obb',
        required=False,
    )
    model_yaml = serializers.CharField(default='yolov8x-obb', required=False)
    model_pt = serializers.CharField(default='yolov8x-obb', required=False)
    data_yaml = serializers.CharField(default='', required=False, allow_blank=True)
    classes = serializers.ListField(child=serializers.CharField(), min_length=1)
    epochs = serializers.IntegerField(default=1000, required=False, min_value=1)
    batch = serializers.IntegerField(default=16, required=False, min_value=1)
    patience = serializers.IntegerField(default=200, required=False, min_value=1)
    imgsz = serializers.IntegerField(default=640, required=False, min_value=32)
    device = serializers.CharField(default='0', required=False, allow_blank=True)
