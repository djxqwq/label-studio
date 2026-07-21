from rest_framework import serializers

from .params import DEFAULT_TRAIN_PARAMS, merge_train_params


class TrainRequestSerializer(serializers.Serializer):
    config_name = serializers.CharField(required=True)
    project_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        required=True,
        help_text='一个或多个项目 ID，合并为训练集',
    )
    train_params = serializers.DictField(required=False)
    epochs = serializers.IntegerField(required=False, min_value=1)
    batch = serializers.IntegerField(required=False)
    patience = serializers.IntegerField(required=False, min_value=1)
    imgsz = serializers.IntegerField(required=False, min_value=32)
    device = serializers.CharField(required=False, allow_blank=True)

    def validated_train_params(self):
        data = self.validated_data
        legacy = {
            k: data[k] for k in ('epochs', 'batch', 'patience', 'imgsz', 'device')
            if k in data
        }
        return merge_train_params(data.get('train_params') or {}, legacy)


class ModelConfigSerializer(serializers.Serializer):
    name = serializers.CharField(required=False)
    task_type = serializers.ChoiceField(
        choices=[('obb', 'OBB'), ('detect', 'Detect'), ('cls', 'CLS'), ('seg', 'SEG')],
        required=False,
    )
    model_yaml = serializers.CharField(required=False)
    model_pt = serializers.CharField(required=False)
    data_yaml = serializers.CharField(required=False, allow_blank=True)
    classes = serializers.ListField(child=serializers.CharField(), required=False)
    train_params = serializers.DictField(required=False)
    epochs = serializers.IntegerField(required=False, min_value=1)
    batch = serializers.IntegerField(required=False)
    patience = serializers.IntegerField(required=False, min_value=1)
    imgsz = serializers.IntegerField(required=False, min_value=32)
    device = serializers.CharField(required=False, allow_blank=True)

    def to_model_fields(self, existing=None):
        data = dict(self.validated_data)
        existing = existing or {}

        name = data.get('name', existing.get('name'))
        classes = data.get('classes', existing.get('classes'))
        if not name:
            raise serializers.ValidationError({'name': '配置名称必填'})
        if not classes:
            raise serializers.ValidationError({'classes': '类别必填'})

        legacy = {
            k: data[k] for k in ('epochs', 'batch', 'patience', 'imgsz', 'device')
            if k in data
        }
        train_params = merge_train_params(
            DEFAULT_TRAIN_PARAMS,
            existing.get('train_params') or {},
            data.get('train_params') or {},
            legacy,
        )
        return {
            'name': name,
            'task_type': data.get('task_type', existing.get('task_type', 'obb')),
            'model_yaml': data.get('model_yaml', existing.get('model_yaml', 'yolov8x-obb')),
            'model_pt': data.get('model_pt', existing.get('model_pt', 'yolov8x-obb')),
            'data_yaml': data.get('data_yaml', existing.get('data_yaml', '')),
            'classes': classes,
            'train_params': train_params,
            'epochs': train_params.get('epochs', 1000),
            'batch': train_params.get('batch', 16),
            'patience': train_params.get('patience', 200),
            'imgsz': train_params.get('imgsz', 640),
            'device': str(train_params.get('device', '0')),
        }
