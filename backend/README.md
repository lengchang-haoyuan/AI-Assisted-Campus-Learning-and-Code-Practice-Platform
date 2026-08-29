# ScholarHub 后端数据库层

## 环境约定

- MySQL 8.0 或更高版本，字符集为 `utf8mb4`，排序规则为 `utf8mb4_0900_ai_ci`。
- 数据库中的 `DATETIME(6)` 统一保存 UTC；Python/API 边界使用带时区的 `datetime`。
- 本地连接信息只写入未提交的 `.env`，不要修改 `.env.example` 保存真实密码。

## 初始化空数据库

先确认目标 MySQL 实例中没有 ScholarHub 业务表，再执行：

```powershell
mysql --user=root --password --execute="source schema.sql"
```

脚本会创建或选择 `scholarhub` 数据库，但不会删除数据库、表或已有数据。遇到同名表时会失败并要求人工检查结构。

## 配置与连接检查

复制 `.env.example` 为 `.env`，仅在本机填写：

```dotenv
DATABASE_URL=mysql+pymysql://用户名:URL编码后的密码@127.0.0.1:3306/scholarhub?charset=utf8mb4
```

然后执行：

```powershell
.\.venv\Scripts\Activate.ps1
python -m scripts.check_database
python -m scripts.verify_database_schema
```

## 结构检查

```powershell
python -m unittest discover -s tests -v
```

结构测试会检查 SQLAlchemy mapper、表和列集合、命名约束与索引、核心删除语义、Workflow 节点归属约束，以及所有表的 MySQL 方言 DDL 编译。`python -m scripts.verify_database_schema` 还会只读对比实际 MySQL 数据库与 Models。
