"""
打卡工具函数 - 校园打卡平台
"""
import math
import requests
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import CheckIn, PointRecord


def calculate_distance(lat1, lng1, lat2, lng2):
    """
    使用Haversine公式计算两点间距离（米）
    """
    R = 6371000  # 地球半径（米）

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def verify_location(user_lat, user_lng, activity_lat, activity_lng, radius=500):
    """
    验证用户位置是否在活动允许范围内

    Args:
        user_lat: 用户纬度
        user_lng: 用户经度
        activity_lat: 活动纬度
        activity_lng: 活动经度
        radius: 允许范围（米）

    Returns:
        (bool, str): (是否通过, 提示信息)
    """
    if not all([user_lat, user_lng, activity_lat, activity_lng]):
        return False, "位置信息不完整"

    distance = calculate_distance(
        float(user_lat), float(user_lng),
        float(activity_lat), float(activity_lng)
    )

    if distance <= radius:
        return True, f"距离活动位置{distance:.0f}米，验证通过"
    else:
        return False, f"距离活动位置{distance:.0f}米，超出允许范围{radius}米"


def get_address_from_coordinates(lat, lng):
    """
    使用高德地图API将坐标转换为地址
    """
    if not settings.AMAP_KEY:
        return f"{lat},{lng}"

    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        'key': settings.AMAP_KEY,
        'location': f"{lng},{lat}",
        'extensions': 'base',
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        if data.get('status') == '1':
            return data['regeocode']['formatted_address']
    except Exception as e:
        # 捕获异常但不中断程序，仅打印日志（生产环境建议用logging）
        print(f"高德地图API调用失败: {str(e)}")

    return f"{lat},{lng}"


def calculate_continuous_days(user, activity=None):
    """
    计算用户连续打卡天数（支持按活动筛选）

    Args:
        user: 用户对象（request.user）
        activity: 可选，活动对象，仅计算该活动的连续打卡

    Returns:
        int: 连续打卡天数
    """
    # 基于已通过审核的打卡记录计算连续天数
    query_kwargs = {'user': user, 'status': 'approved'}
    if activity:
        query_kwargs['activity'] = activity

    checkin_dates = list(
        CheckIn.objects.filter(**query_kwargs)
        .values_list('check_in_date', flat=True)
        .distinct()
        .order_by('-check_in_date')
    )
    if not checkin_dates:
        return 0

    continuous_days = 0
    today = timezone.now().date()
    last_checkin_date = checkin_dates[0]

    # 最新打卡若不在今天/昨天，视为已中断
    if last_checkin_date != today and (today - last_checkin_date).days > 1:
        return 0

    # 从最近一天往前递减统计连续天数
    cursor = last_checkin_date
    checkin_date_set = set(checkin_dates)
    while cursor in checkin_date_set:
        continuous_days += 1
        cursor -= timedelta(days=1)

    # 兼容旧逻辑：若最新打卡是昨天/今天且只有一天记录，返回1
    if continuous_days == 0 and checkin_dates:
        continuous_days = 1

    return continuous_days


def award_points(user, activity, streak_days=1, related_checkin=None):
    """
    给用户发放打卡积分并记录积分流水。
    - 基础分：activity.points
    - 连续奖励：连续每满7天 +5 分（最多 +20）
    返回：本次发放积分（int）
    """
    base_points = int(getattr(activity, 'points', 10) or 10)
    streak_days = int(streak_days or 0)
    bonus = min((streak_days // 7) * 5, 20)
    final_points = base_points + bonus

    user.points += final_points
    user.total_checkins += 1
    user.save(update_fields=['points', 'total_checkins'])

    PointRecord.objects.create(
        user=user,
        points=final_points,
        reason=f'打卡奖励 - {activity.title}',
        related_checkin=related_checkin
    )

    return final_points
