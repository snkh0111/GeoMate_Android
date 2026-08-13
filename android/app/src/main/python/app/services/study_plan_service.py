"""Study Plan service — CRUD, daily grouping, stats, and seed data.

Generates a realistic 7-day study plan aligned with the Weihai
field practice schedule from the course PDFs.
"""

import logging
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.study_plan import StudyPlan
from app.schemas.study_plan import PlanCreate, PlanUpdate

logger = logging.getLogger(__name__)


class StudyPlanService:
    """Study plan CRUD + seed operations."""

    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ────────────────────────────────────────────────

    def list_plans(
        self,
        user_id: int | None = None,
        plan_date: date | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> list[StudyPlan]:
        """List plans with optional filters."""
        stmt = select(StudyPlan).order_by(StudyPlan.plan_date, StudyPlan.order_index)

        if user_id is not None:
            stmt = stmt.where(StudyPlan.user_id == user_id)
        if plan_date is not None:
            stmt = stmt.where(StudyPlan.plan_date == plan_date)
        if status is not None:
            stmt = stmt.where(StudyPlan.status == status)
        if category is not None:
            stmt = stmt.where(StudyPlan.category == category)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def get_plan(self, plan_id: int) -> StudyPlan | None:
        """Get a single plan item."""
        return self.db.get(StudyPlan, plan_id)

    def create_plan(self, data: PlanCreate) -> StudyPlan:
        """Create a new plan item."""
        plan = StudyPlan(**data.dict())
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update_plan(self, plan_id: int, data: PlanUpdate) -> StudyPlan | None:
        """Update a plan item. Only provided fields are changed."""
        plan = self.db.get(StudyPlan, plan_id)
        if not plan:
            return None
        update_data = data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(plan, key, value)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def toggle_status(self, plan_id: int) -> StudyPlan | None:
        """Toggle a plan between pending and completed."""
        plan = self.db.get(StudyPlan, plan_id)
        if not plan:
            return None
        plan.status = "completed" if plan.status == "pending" else "pending"
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete_plan(self, plan_id: int) -> bool:
        """Delete a plan item."""
        plan = self.db.get(StudyPlan, plan_id)
        if not plan:
            return False
        self.db.delete(plan)
        self.db.commit()
        return True

    # ── Grouped queries ─────────────────────────────────────

    def get_daily_plans(
        self, user_id: int, plan_date: date | None = None
    ) -> list[dict]:
        """Get plans grouped by day, with completion stats per day.

        Returns a list of dicts suitable for the checkbox UI:
        [{date, total_tasks, completed_tasks, completion_rate, items: [...]}]
        """
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.user_id == user_id)
            .order_by(StudyPlan.plan_date, StudyPlan.order_index)
        )
        if plan_date:
            stmt = stmt.where(StudyPlan.plan_date == plan_date)

        result = self.db.execute(stmt)
        plans = result.scalars().all()

        # Group by date
        by_date: dict[date, list[StudyPlan]] = {}
        for p in plans:
            by_date.setdefault(p.plan_date, []).append(p)

        daily = []
        for d in sorted(by_date.keys()):
            items = by_date[d]
            completed = sum(1 for p in items if p.status == "completed")
            daily.append({
                "date": d.isoformat(),
                "total_tasks": len(items),
                "completed_tasks": completed,
                "completion_rate": round(completed / len(items), 2) if items else 0,
                "items": items,
            })

        return daily

    def get_stats(self, user_id: int) -> dict:
        """Get overall study statistics for a user."""
        stmt = select(StudyPlan).where(StudyPlan.user_id == user_id)
        result = self.db.execute(stmt)
        plans = result.scalars().all()

        total = len(plans)
        completed = sum(1 for p in plans if p.status == "completed")
        rate = round(completed / total, 2) if total else 0

        # By category
        by_cat: dict[str, dict] = {}
        for p in plans:
            cat = p.category or "未分类"
            if cat not in by_cat:
                by_cat[cat] = {"total": 0, "completed": 0}
            by_cat[cat]["total"] += 1
            if p.status == "completed":
                by_cat[cat]["completed"] += 1
        for cat in by_cat:
            t = by_cat[cat]["total"]
            c = by_cat[cat]["completed"]
            by_cat[cat]["rate"] = round(c / t, 2)

        # By priority
        by_pri: dict[str, dict] = {}
        for p in plans:
            pri = p.priority
            if pri not in by_pri:
                by_pri[pri] = {"total": 0, "completed": 0}
            by_pri[pri]["total"] += 1
            if p.status == "completed":
                by_pri[pri]["completed"] += 1
        for pri in by_pri:
            t = by_pri[pri]["total"]
            c = by_pri[pri]["completed"]
            by_pri[pri]["rate"] = round(c / t, 2)

        return {
            "total_tasks": total,
            "completed_tasks": completed,
            "completion_rate": rate,
            "by_category": by_cat,
            "by_priority": by_pri,
        }

    # ── Seed ────────────────────────────────────────────────

    def seed_plans(self, user_id: int, force: bool = False) -> dict:
        """Generate a 7-day study plan for a user.

        The plan follows the actual Weihai field practice schedule:
        Day 1: Station training + safety
        Day 2-7: One route per day + daily mineral/rock review + exam prep

        Args:
            user_id: The user to create plans for.
            force: If True, delete existing plans for this user first.

        Returns:
            Dict with created and skipped counts.
        """
        # Check existing
        existing = self.db.scalar(
            select(func.count(StudyPlan.id)).where(StudyPlan.user_id == user_id)
        )
        if existing and existing > 0:
            if not force:
                logger.info("Plans already exist for user %d (%d items), skipping", user_id, existing)
                return {"created": 0, "skipped": existing}
            else:
                self.db.execute(
                    StudyPlan.__table__.delete().where(StudyPlan.user_id == user_id)
                )
                self.db.commit()

        plans_data = self._build_7day_plan(user_id)
        created = 0
        for data in plans_data:
            plan = StudyPlan(**data)
            self.db.add(plan)
            created += 1

        self.db.commit()
        logger.info("Seeded %d plans for user %d", created, user_id)
        return {"created": created, "skipped": 0}

    @staticmethod
    def _build_7day_plan(user_id: int) -> list[dict]:
        """Build the 7-day study plan matching the actual field practice.

        Reference schedule from the course PDF:
        - 站内教学 → 路线一 → 路线二 → 路线三 → 路线四 → 路线五 → 路线六 → 路线七
        """
        today = date.today()

        def day(offset: int) -> date:
            return today.replace(day=today.day + offset) if False else _make_date(today, offset)

        return [
            # ═══════════════════════════════════════════════════
            # Day 1: 站内教学 — 基本技能 + 安全规范
            # ═══════════════════════════════════════════════════
            {
                "user_id": user_id, "plan_date": _make_date(today, 0),
                "route_id": None, "order_index": 1,
                "category": "技能", "priority": "high", "status": "pending",
                "task_name": "罗盘的结构认知与使用方法",
                "content": "认识罗盘各部件（磁针、刻度盘、水准器、瞄准器）。掌握调节磁偏角的方法。学习测量走向、倾向、倾角的三步骤。\n\n⚠️ 高频易错：在下层面测量时倾向容易读反180°；测量前未将水准泡完全居中。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 0),
                "route_id": None, "order_index": 2,
                "category": "技能", "priority": "high", "status": "pending",
                "task_name": "野簿记录规范与地质素描",
                "content": "掌握野簿排版规则：右页文字，左页素描图，全程铅笔。\n记录格式：页眉(日期+天气+地点) → 路线号 → 地质点编号[NO.X] → 点位与点义 → 产状数据 → 标本编号。\n\n地质素描五要素：图名、图内容、图例、方位、比例尺，缺一不可。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 0),
                "route_id": None, "order_index": 3,
                "category": "安全", "priority": "high", "status": "pending",
                "task_name": "野外安全规范学习（一票否决条款）",
                "content": "牢记六条一票否决红线：\n1. 发生安全事故或严重违反安全管理规定\n2. 私自下海游泳\n3. 发生打架斗殴行为\n4. 累计2天及以上无故不出野外\n5. 罗盘使用、产状测量等基本技能考核不合格\n6. 经常不带地质三大件\n\n此外：野外必须长衣长裤硬底运动鞋，携带罗盘、放大镜、地质锤三大件。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 0),
                "route_id": None, "order_index": 4,
                "category": "矿物", "priority": "medium", "status": "pending",
                "task_name": "核心造岩矿物预习（一）",
                "content": "预习石英、斜长石、钾长石的鉴定特征。\n\n重点对比：\n- 石英 vs 斜长石：石英无解理+油脂光泽+贝壳状断口；斜长石有解理+可见聚片双晶纹\n- 斜长石 vs 钾长石：斜长石灰白色+聚片双晶；钾长石肉红色+卡氏双晶",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 0),
                "route_id": None, "order_index": 5,
                "category": "矿物", "priority": "medium", "status": "pending",
                "task_name": "核心造岩矿物预习（二）",
                "content": "预习角闪石、辉石、橄榄石的鉴定特征。\n\n重点对比：\n- 角闪石 vs 辉石：角闪石长柱状+解理夹角56°/124°；辉石短柱状+解理夹角近90°\n- 橄榄石：橄榄绿色+粒状+无解理+极易风化为蛇纹石（马山玄武岩中的代表性矿物）",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 0),
                "route_id": None, "order_index": 6,
                "category": "考试", "priority": "medium", "status": "pending",
                "task_name": "了解威海地质实习整体安排",
                "content": "阅读教学大纲：\n- 7条路线概览：占甲埠→马山→棉花山→刘公岛→鸡鸣岛→奔腾码头→黄沟村\n- 外动力地质作用：风化(鸡鸣岛)、海洋(刘公岛/棉花山/奔腾码头/鸡鸣岛)、河流(鸡鸣岛)\n- 内动力地质作用：岩浆(福山/占甲埠/鸡鸣岛)、构造(奔腾码头/刘公岛/棉花山/黄沟村)、变质(奔腾码头/刘公岛)",
            },

            # ═══════════════════════════════════════════════════
            # Day 2: 路线一 — 占甲埠村花岗岩路线
            # ═══════════════════════════════════════════════════
            {
                "user_id": user_id, "plan_date": _make_date(today, 1),
                "route_id": 1, "order_index": 1,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【路线一预习】占甲埠村 — 花岗岩基本特征",
                "content": "预习重点：\n1. 玲珑岩体花岗岩的结构类型（等粒结构 vs 似斑状结构）\n2. 块状构造的特征\n3. 主要造岩矿物识别：钾长石（肉红色）、斜长石（灰白色）、石英（油脂光泽）、角闪石（长柱状黑色）、黑云母\n4. 理解穿切关系：花岗伟晶岩脉、辉绿岩脉 → 判断侵入先后期次",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 1),
                "route_id": 1, "order_index": 2,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【野外实践】占甲埠村野外观察与记录",
                "content": "野外任务：\n☐ 观察花岗岩的结构与构造\n☐ 鉴别钾长石、斜长石、石英、角闪石\n☐ 识别脉岩穿切关系\n☐ 采集代表性岩石标本（编号SGD-01起）\n☐ 记录产状数据\n☐ 完成野簿记录（含素描图）\n\n⚠️ 注意：需爬山，场地拥挤。按小组采集标本。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 1),
                "route_id": 1, "order_index": 3,
                "category": "岩石", "priority": "medium", "status": "pending",
                "task_name": "侵入岩知识巩固",
                "content": "复习要点：\n1. 侵入岩与喷出岩的区别（冷却速度→晶体大小→结构）\n2. 等粒结构与似斑状结构的成因\n3. 脉岩的概念及穿切关系的判断方法\n4. 花岗岩中石英含量通常>20%，斜长石>钾长石（玲珑岩体）",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 1),
                "route_id": None, "order_index": 4,
                "category": "矿物", "priority": "medium", "status": "pending",
                "task_name": "石英和斜长石的野外快速鉴别",
                "content": "今日重点对比练习：\n- 石英：无解理面、油脂光泽、硬度7（小刀刻不动）、贝壳状断口\n- 斜长石：灰白色、两组完全解理、用放大镜看晶面可见平行聚片双晶纹\n\n💡 技巧：用放大镜看新鲜断口——石英呈贝壳状，斜长石呈阶梯状（解理面）。",
            },

            # ═══════════════════════════════════════════════════
            # Day 3: 路线二 — 马山古火山路线
            # ═══════════════════════════════════════════════════
            {
                "user_id": user_id, "plan_date": _make_date(today, 2),
                "route_id": 2, "order_index": 1,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【路线二预习】马山 — 玄武岩与火山机构",
                "content": "预习重点：\n1. 玄武岩的岩性特征（暗色、细粒、基性）\n2. 柱状节理的形成机理——岩浆冷却收缩→多边形柱状断裂\n3. 气孔构造 vs 杏仁构造的区别\n4. 火山碎屑岩类型：火山角砾岩、凝灰岩\n5. 橄榄石和辉石的识别（马山玄武岩代表性矿物）",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 2),
                "route_id": 2, "order_index": 2,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【野外实践】马山野外观察与剖面图绘制",
                "content": "野外任务：\n☐ 观察柱状节理并理解其形成机理\n☐ 区分气孔构造与杏仁构造\n☐ 识别橄榄石（橄榄绿色粒状）和辉石（短柱状暗绿色）\n☐ 观察火山碎屑岩（角砾岩、凝灰岩）\n☐ 判断火山喷出期次\n☐ 绘制火山岩剖面图\n\n⚠️ 往返>4小时，自备干粮和水。沿马路注意安全。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 2),
                "route_id": None, "order_index": 3,
                "category": "构造", "priority": "medium", "status": "pending",
                "task_name": "柱状节理的形成机理",
                "content": "深入理解：\n1. 玄武岩熔岩流冷却时，表面先冷缩→产生张力→形成垂直于冷却面的多边形裂缝\n2. 裂缝向内部扩展→形成六边形（或其他多边形）柱体\n3. 柱体直径取决于冷却速度：冷却越快→柱体越细\n\n💡 柱状节理不仅见于玄武岩，流纹岩、凝灰岩中也可发育。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 2),
                "route_id": None, "order_index": 4,
                "category": "矿物", "priority": "medium", "status": "pending",
                "task_name": "角闪石和辉石的区别练习",
                "content": "马山路线重点对比：\n- 辉石：短柱状、暗绿色至黑褐色、解理夹角~90°（近正交）\n- 角闪石：长柱状/针状、黑褐色至深绿色、解理夹角56°/124°\n\n💡 口诀：辉短角长，辉直（90°）角斜（56°）。",
            },

            # ═══════════════════════════════════════════════════
            # Day 4: 路线三 — 棉花山沉积岩路线
            # ═══════════════════════════════════════════════════
            {
                "user_id": user_id, "plan_date": _make_date(today, 3),
                "route_id": 3, "order_index": 1,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【路线三预习】棉花山 — 沉积岩与古湖泊环境",
                "content": "预习重点：\n1. 龙旺庄组碎屑岩的颗粒描述：成分、粒度、磨圆度、分选性\n2. 常见沉积构造：平行层理、交错层理、波痕、泥裂\n3. 软沉积变形构造的成因（液化砂岩脉、卷曲层理）\n4. 古湖泊沉积环境的分析方法",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 3),
                "route_id": 3, "order_index": 2,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【野外实践】棉花山野外观察与记录",
                "content": "野外任务：\n☐ 描述碎屑岩的颗粒特征（成分、粒度、磨圆、分选）\n☐ 识别并素描波痕和泥裂\n☐ 观察软沉积变形构造\n☐ 分析古湖泊沉积环境\n☐ 完成野簿记录\n\n⚠️ 必须穿硬底鞋（礁石锋利）。注意潮汐。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 3),
                "route_id": None, "order_index": 3,
                "category": "岩石", "priority": "medium", "status": "pending",
                "task_name": "沉积岩基础知识复习",
                "content": "三大类岩石对比复习——沉积岩部分：\n1. 沉积岩的野外鉴定标志：层理构造、含有化石、碎屑颗粒\n2. 沉积构造的成因分类\n3. 粒度与沉积环境的关系\n4. 化学沉积岩 vs 碎屑沉积岩",
            },

            # ═══════════════════════════════════════════════════
            # Day 5: 路线四 — 刘公岛基岩海岸
            # ═══════════════════════════════════════════════════
            {
                "user_id": user_id, "plan_date": _make_date(today, 4),
                "route_id": 4, "order_index": 1,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【路线四预习】刘公岛 — 变质岩与基岩海岸地貌",
                "content": "预习重点：\n1. 花岗片麻岩的片麻状构造（暗色矿物与浅色矿物条带状定向排列）\n2. 石香肠构造（布丁构造）的形成机制\n3. 海蚀地貌：海蚀崖、海蚀穴、海蚀平台\n4. 变质作用类型（区域变质）\n5. 甲午海战历史背景",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 4),
                "route_id": 4, "order_index": 2,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【野外实践】刘公岛野外观察与记录",
                "content": "野外任务：\n☐ 观察海蚀崖、海蚀穴、海蚀平台\n☐ 识别花岗片麻岩的片麻状构造\n☐ 观察石香肠构造\n☐ 观察生物对强水动力环境的适应\n☐ 参观甲午海战纪念馆\n\n⚠️ 必须在17:00前乘船返回！严禁带地质锤上岛。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 4),
                "route_id": None, "order_index": 3,
                "category": "地貌", "priority": "medium", "status": "pending",
                "task_name": "海岸地貌知识学习",
                "content": "基岩海岸 vs 沙质海岸：\n1. 基岩海岸：波浪侵蚀为主→海蚀崖、海蚀穴、海蚀平台\n2. 沙质海岸：波浪堆积为主→沙滩、沙坝、沿岸流搬运\n3. 生物海岸：珊瑚礁、红树林（威海较少见）\n\n💡 刘公岛是典型的基岩海岸，鸡鸣岛是沙质海岸。",
            },

            # ═══════════════════════════════════════════════════
            # Day 6: 路线五 — 鸡鸣岛-朝阳港-那香海
            # ═══════════════════════════════════════════════════
            {
                "user_id": user_id, "plan_date": _make_date(today, 5),
                "route_id": 5, "order_index": 1,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【路线五预习】鸡鸣岛 — 风化作用与沙质海岸",
                "content": "预习重点：\n1. 物理风化 vs 化学风化的识别\n2. 风化壳剖面的分层特征\n3. 沙质海岸的水动力条件\n4. 沿岸泥沙搬运与堆积地形（沙滩、沙坝）\n5. 河流-海洋相互作用\n6. 滨海工程地质问题",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 5),
                "route_id": 5, "order_index": 2,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【野外实践】鸡鸣岛-朝阳港-那香海野外观察",
                "content": "野外任务：\n☐ 观察鸡鸣岛玄武岩风化壳剖面\n☐ 识别物理风化（球形风化、节理风化）与化学风化（氧化铁染色）现象\n☐ 观察朝阳港沙滩砂粒成分与粒度\n☐ 观察那香海沙坝形态\n☐ 观察沿岸泥沙搬运方向\n\n⚠️ 严禁下海游泳！注意潮汐变化。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 5),
                "route_id": None, "order_index": 3,
                "category": "地貌", "priority": "medium", "status": "pending",
                "task_name": "风化作用知识巩固",
                "content": "鸡鸣岛路线重点理解：\n1. 物理风化——岩石破碎但化学成分不变（温差、冰劈、盐晶、生物物理）\n2. 化学风化——岩石化学成分改变（溶解、氧化、水解、水化）\n3. 风化壳剖面：自上而下→土壤层→残积层→半风化岩石→新鲜基岩\n\n💡 球形风化：沿节理面优先风化，使岩块趋于球形。",
            },

            # ═══════════════════════════════════════════════════
            # Day 7: 路线六+七 + 综合复习
            # ═══════════════════════════════════════════════════
            {
                "user_id": user_id, "plan_date": _make_date(today, 6),
                "route_id": 6, "order_index": 1,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【路线六预习】奔腾码头 — 变质构造与显微构造",
                "content": "预习重点：\n1. 三类变质岩鉴别：长英质片麻岩（片麻状构造）、大理岩（滴酸起泡）、榴辉岩（绿辉石+石榴子石）\n2. 显微构造的放大镜观察\n3. 基岩海岸地貌\n\n⚠️ 必须落潮时观测，查看潮汐表。礁石湿滑。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 6),
                "route_id": 7, "order_index": 2,
                "category": "路线复习", "priority": "high", "status": "pending",
                "task_name": "【路线七预习】黄沟村 — 岩浆岩与硫化物矿产",
                "content": "预习重点：\n1. 伟德山岩体花岗岩 vs 玲珑岩体花岗岩对比\n2. 断层构造证据：擦痕、断层角砾岩\n3. 热液硫化物矿化：黄铁矿（立方体）、黄铜矿（铜黄色金属光泽）\n4. 郭永怀科学家精神\n\n⚠️ 观测场地狭小。",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 6),
                "route_id": None, "order_index": 3,
                "category": "考试", "priority": "high", "status": "pending",
                "task_name": "综合复习：三大类岩石对比总结",
                "content": "考试高频考点——三大类岩石对比：\n\n| 类型 | 结构 | 构造 | 代表岩石 | 实习路线 |\n|------|------|------|----------|----------|\n| 岩浆岩-侵入 | 等粒/似斑状 | 块状 | 花岗岩 | 路线一、七 |\n| 岩浆岩-喷出 | 隐晶/斑状 | 气孔/杏仁/柱状节理 | 玄武岩 | 路线二 |\n| 沉积岩 | 碎屑/化学 | 层理/波痕/泥裂 | 砂岩/页岩 | 路线三 |\n| 变质岩 | 变晶 | 片麻状/片状 | 片麻岩/大理岩 | 路线四、六 |",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 6),
                "route_id": None, "order_index": 4,
                "category": "考试", "priority": "high", "status": "pending",
                "task_name": "综合复习：七条路线速查表记忆",
                "content": "必须记住七条路线的核心内容：\n1. 占甲埠→花岗岩+穿切关系\n2. 马山→玄武岩+柱状节理+橄榄石辉石\n3. 棉花山→碎屑岩+沉积构造+软沉积变形\n4. 刘公岛→基岩海岸+花岗片麻岩+石香肠\n5. 鸡鸣岛→沙质海岸+风化壳+沙滩沙坝\n6. 奔腾码头→片麻岩+大理岩+榴辉岩+潮汐控制\n7. 黄沟村→伟德山花岗岩+硫化物+郭永怀",
            },
            {
                "user_id": user_id, "plan_date": _make_date(today, 6),
                "route_id": None, "order_index": 5,
                "category": "安全", "priority": "medium", "status": "pending",
                "task_name": "考前最终检查：罗盘产状测量自测",
                "content": "自检罗盘测量准确性：\n☐ 能独立完成磁偏角调节\n☐ 能正确测量岩层走向（长边贴层面→水准泡居中→读北针）\n☐ 能正确测量倾向（短边贴层面→沿最大倾斜线→水准泡居中→读倾斜针）\n☐ 能正确测量倾角（侧立罗盘→长边贴倾斜线→调杠杆→读刻度）\n☐ 不会将倾向读反180°\n☐ 不会混淆北针与南针",
            },
        ]


def _make_date(base: date, offset_days: int) -> date:
    """Create a date relative to base date."""
    from datetime import timedelta
    return base + timedelta(days=offset_days)
