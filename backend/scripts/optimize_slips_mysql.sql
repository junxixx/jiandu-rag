-- 牍库大表优化（DeepJiandu 全量导入后建议在维护窗口执行）
-- 使用前请备份数据库。执行后在 .env 设置 SLIPS_USE_FULLTEXT=1 并重启后端。

-- 1) 中文等多字节全文检索：需 ngram 解析器（MySQL 5.7.6+ / 8.0）
--    若尚未配置，可在 my.cnf 增加后重启 MySQL：
--    [mysqld]
--    ngram_token_size = 2
--    innodb_ft_min_token_len = 1
--    innodb_ft_max_token_len = 84
--    详见：https://dev.mysql.com/doc/refman/8.0/en/fulltext-search-ngram.html

-- 2) 添加全文索引（若已存在同名索引请先 DROP）
-- ALTER TABLE bamboo_slips DROP INDEX ft_bamboo_slips;
ALTER TABLE bamboo_slips
  ADD FULLTEXT INDEX ft_bamboo_slips (title, transcription, vernacular) WITH PARSER ngram;

-- 3) 可选：按数据来源筛列表时可用（若后续 API 支持 tags / site_name 过滤）
-- CREATE INDEX idx_bamboo_slips_site ON bamboo_slips (site_name(64));
-- CREATE INDEX idx_bamboo_slips_tags ON bamboo_slips (tags(128));
