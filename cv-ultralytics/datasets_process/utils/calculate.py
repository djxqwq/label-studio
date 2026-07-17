import statistics


def get_label_median(results, cls=None):
    """
    获取标签长、宽的中位数
    :param results:
    :param cls:
    :return:
    """
    # 使用列表推导式，并增加条件判断
    width = [box.xywhr[0][2] for r in results for box in r.obb if int(box.cls[0]) == cls] if cls is not None else [
        box.xywhr[0][2] for r in results for box in r.obb]
    height = [box.xywhr[0][3] for r in results for box in r.obb if int(box.cls[0]) == cls] if cls is not None else [
        box.xywhr[0][3] for r in results for box in r.obb]

    # 如果列表不为空，计算中位数，否则返回None
    med_w = statistics.median(width) if width else 0
    med_h = statistics.median(height) if height else 0

    return med_w, med_h