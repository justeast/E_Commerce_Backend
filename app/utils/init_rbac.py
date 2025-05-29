"""
初始化RBAC系统
"""
import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

from app.db.session import async_session
from app.models.rbac import Role, Permission
from app.models.user import User

# 默认权限列表
DEFAULT_PERMISSIONS = [
    # 用户管理权限
    {"name": "查看用户列表", "code": "user:list", "description": "查看所有用户的列表"},
    {"name": "查看用户详情", "code": "user:read", "description": "查看用户的详细信息"},
    {"name": "创建用户", "code": "user:create", "description": "创建新用户"},
    {"name": "更新用户", "code": "user:update", "description": "更新用户信息"},
    {"name": "删除用户", "code": "user:delete", "description": "删除用户"},
    {"name": "更新用户角色", "code": "user:update_roles", "description": "更新用户的角色"},

    # 角色管理权限
    {"name": "查看角色列表", "code": "role:list", "description": "查看所有角色的列表"},
    {"name": "查看角色详情", "code": "role:read", "description": "查看角色的详细信息"},
    {"name": "创建角色", "code": "role:create", "description": "创建新角色"},
    {"name": "更新角色", "code": "role:update", "description": "更新角色信息"},
    {"name": "删除角色", "code": "role:delete", "description": "删除角色"},

    # 权限管理权限
    {"name": "查看权限列表", "code": "permission:list", "description": "查看所有权限的列表"},
    {"name": "查看权限详情", "code": "permission:read", "description": "查看权限的详细信息"},
    {"name": "创建权限", "code": "permission:create", "description": "创建新权限"},
    {"name": "更新权限", "code": "permission:update", "description": "更新权限信息"},
    {"name": "删除权限", "code": "permission:delete", "description": "删除权限"},

    # 商品管理权限（预留）
    {"name": "查看商品列表", "code": "product:list", "description": "查看所有商品的列表"},
    {"name": "查看商品详情", "code": "product:read", "description": "查看商品的详细信息"},
    {"name": "创建商品", "code": "product:create", "description": "创建新商品"},
    {"name": "更新商品", "code": "product:update", "description": "更新商品信息"},
    {"name": "删除商品", "code": "product:delete", "description": "删除商品"},
]

# 默认角色列表
DEFAULT_ROLES = [
    {
        "name": "超级管理员",
        "description": "拥有所有权限的超级管理员",
        "permissions": ["*"]  # 所有权限
    },
    {
        "name": "用户管理员",
        "description": "负责用户管理的管理员",
        "permissions": ["user:list", "user:read", "user:create", "user:update", "user:delete", "user:update_roles"]
    },
    {
        "name": "商品管理员",
        "description": "负责商品管理的管理员",
        "permissions": ["product:list", "product:read", "product:create", "product:update", "product:delete"]
    },
    {
        "name": "普通用户",
        "description": "普通用户角色",
        "permissions": []  # 无特殊权限
    }
]


async def init_permissions(db: AsyncSession) -> dict:
    """
    初始化权限
    """
    logging.info("初始化权限...")
    permissions_map = {}

    for perm_data in DEFAULT_PERMISSIONS:
        # 检查权限是否已存在
        result = await db.execute(
            select(Permission).where(Permission.code == perm_data["code"])
        )
        existing_perm = result.scalars().first()

        if existing_perm:
            permissions_map[perm_data["code"]] = existing_perm
            continue

        # 创建新权限
        new_perm = Permission(
            name=perm_data["name"],
            code=perm_data["code"],
            description=perm_data["description"]
        )
        db.add(new_perm)
        await db.flush()  # 刷新以获取ID
        permissions_map[perm_data["code"]] = new_perm

    await db.commit()
    logging.info(f"已初始化 {len(permissions_map)} 个权限")
    return permissions_map


async def init_roles(db: AsyncSession, permissions_map: dict):
    """
    初始化角色
    """
    logging.info("初始化角色...")
    roles_count = 0

    for role_data in DEFAULT_ROLES:
        # 检查角色是否已存在
        result = await db.execute(
            select(Role).where(Role.name == role_data["name"])
        )
        existing_role = result.scalars().first()

        if existing_role:
            # 先获取现有权限，避免延迟加载问题
            await db.refresh(existing_role, ["permissions"])

            # 更新现有角色的权限
            if role_data["name"] == "超级管理员":
                # 超级管理员拥有所有权限
                # 使用关联表直接操作而不是替换整个集合
                existing_role.permissions.clear()
                for perm in permissions_map.values():
                    existing_role.permissions.append(perm)
            else:
                # 其他角色根据配置分配权限
                existing_role.permissions.clear()
                for perm_code in role_data["permissions"]:
                    if perm_code in permissions_map:
                        existing_role.permissions.append(permissions_map[perm_code])

            roles_count += 1
            continue

        # 创建新角色
        new_role = Role(
            name=role_data["name"],
            description=role_data["description"]
        )

        # 分配权限
        if role_data["name"] == "超级管理员":
            # 超级管理员拥有所有权限
            for perm in permissions_map.values():
                new_role.permissions.append(perm)
        else:
            # 其他角色根据配置分配权限
            for perm_code in role_data["permissions"]:
                if perm_code in permissions_map:
                    new_role.permissions.append(permissions_map[perm_code])

        db.add(new_role)
        roles_count += 1

    await db.commit()
    logging.info(f"已初始化 {roles_count} 个角色")


async def assign_admin_role(db: AsyncSession, admin_email: str = "qyd@qq.com"):
    """
    为管理员用户分配超级管理员角色
    """
    try:
        # 查找管理员用户
        result = await db.execute(
            select(User).where(User.email == admin_email)
        )
        admin_user = result.scalars().first()

        if not admin_user:
            logging.warning(f"未找到管理员用户 {admin_email}，跳过角色分配")
            return

        # 查找超级管理员角色
        result = await db.execute(
            select(Role).where(Role.name == "超级管理员")
        )
        admin_role = result.scalars().first()

        if not admin_role:
            logging.warning("未找到超级管理员角色，跳过角色分配")
            return

        # 预加载用户的角色，避免延迟加载问题
        await db.refresh(admin_user, ["roles"])

        # 检查用户是否已有该角色
        user_has_role = False
        for role in admin_user.roles:
            if role.id == admin_role.id:
                user_has_role = True
                break

        # 分配角色
        if not user_has_role:
            # 使用直接的SQL语句添加角色关联
            await db.execute(
                text(
                    "INSERT INTO user_role (user_id, role_id) VALUES (:user_id, :role_id) "
                    "ON DUPLICATE KEY UPDATE user_id=user_id"
                ),
                {"user_id": admin_user.id, "role_id": admin_role.id}
            )
            await db.commit()
            logging.info(f"已为用户 {admin_email} 分配超级管理员角色")
        else:
            logging.info(f"用户 {admin_email} 已拥有超级管理员角色")
    except Exception as e:
        logging.error(f"为管理员分配角色时出错: {str(e)}")
        await db.rollback()
        raise


async def init_rbac():
    """
    初始化RBAC系统
    """
    logging.info("开始初始化RBAC系统...")

    # 获取数据库会话
    async with async_session() as db:
        try:
            # 初始化权限
            permissions_map = await init_permissions(db)

            # 初始化角色
            await init_roles(db, permissions_map)

            # 为管理员用户分配超级管理员角色
            await assign_admin_role(db)

            logging.info("RBAC系统初始化完成")
        except Exception as e:
            logging.error(f"RBAC系统初始化失败: {str(e)}")
            raise


# 如果直接运行此脚本，则执行初始化
if __name__ == "__main__":
    asyncio.run(init_rbac())
