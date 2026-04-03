/*
 Navicat Premium Dump SQL

 Source Server         : localhost_3306_mysql
 Source Server Type    : MySQL
 Source Server Version : 50714 (5.7.14)
 Source Host           : localhost:3306
 Source Schema         : social_platforms_analysis

 Target Server Type    : MySQL
 Target Server Version : 50714 (5.7.14)
 File Encoding         : 65001

 Date: 03/04/2026 00:05:07
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for fact_topic_stats
-- ----------------------------
DROP TABLE IF EXISTS `fact_topic_stats`;
CREATE TABLE `fact_topic_stats`  (
  `window_start` bigint(20) NOT NULL COMMENT '窗口开始时间 (毫秒)',
  `window_end` bigint(20) NOT NULL COMMENT '窗口结束时间 (毫秒)',
  `topic_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '话题名称',
  `avg_sentiment` float NULL DEFAULT 0 COMMENT '平均情感分',
  `hotspot_count` int(11) NULL DEFAULT 0 COMMENT '热搜条目数',
  `alert_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT 'NORMAL' COMMENT '预警等级',
  PRIMARY KEY (`window_start`, `topic_name`) USING BTREE,
  INDEX `idx_topic`(`topic_name`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '话题统计结果表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for sys_user
-- ----------------------------
DROP TABLE IF EXISTS `sys_user`;
CREATE TABLE `sys_user`  (
  `user_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `account` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录账户(需唯一)',
  `password` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密码(建议存储密文,如BCrypt)',
  `role_type` tinyint(4) NOT NULL DEFAULT 1 COMMENT '用户身份: 1-客户, 2-业务管理员, 3-系统管理员',
  `nickname` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '昵称',
  `email` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '邮箱',
  `register_ip` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '注册时的IP地址(长度45以兼容IPv6)',
  `register_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  `gender` tinyint(4) NULL DEFAULT 0 COMMENT '性别: 0-未知, 1-男, 2-女',
  `signature` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '个性签名',
  `avatar` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '头像链接地址',
  PRIMARY KEY (`user_id`) USING BTREE,
  UNIQUE INDEX `uk_account`(`account`) USING BTREE COMMENT '账户名必须唯一'
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '系统用户信息表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for user_login_log
-- ----------------------------
DROP TABLE IF EXISTS `user_login_log`;
CREATE TABLE `user_login_log`  (
  `log_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '日志主键ID',
  `user_id` bigint(20) NOT NULL COMMENT '关联的用户ID(外键)',
  `login_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '本次登录时间',
  `login_ip` varchar(45) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL COMMENT '本次登录的IP地址',
  PRIMARY KEY (`log_id`) USING BTREE,
  INDEX `idx_user_id`(`user_id`) USING BTREE COMMENT '为外键字段建立普通索引，加速查询',
  CONSTRAINT `fk_log_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci COMMENT = '用户登录流水表' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for weibo_analysis
-- ----------------------------
DROP TABLE IF EXISTS `weibo_analysis`;
CREATE TABLE `weibo_analysis`  (
  `item_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '主键：MD5(title)',
  `sentiment_score` float NULL DEFAULT 0 COMMENT '情感分数 (-1 到 1 或 0 到 1，需与 NLP 库一致)',
  `topic_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '话题名称 (扁平化)',
  `type_name` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '未知' COMMENT '内容类型 (娱乐/社会/科技等)',
  `nlp_time` bigint(20) NOT NULL COMMENT '分析时间戳 (毫秒)',
  `update_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`item_id`) USING BTREE,
  INDEX `idx_topic_name`(`topic_name`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '微博热搜分析结果表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for weibo_base
-- ----------------------------
DROP TABLE IF EXISTS `weibo_base`;
CREATE TABLE `weibo_base`  (
  `item_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '主键：MD5(title)',
  `title` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '热搜标题',
  `url` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '跳转链接',
  `first_time` bigint(20) NOT NULL COMMENT '首次上榜时间戳 (毫秒)',
  `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (`item_id`) USING BTREE,
  INDEX `idx_title`(`title`(100)) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '微博历史总热搜表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for weibo_trend
-- ----------------------------
DROP TABLE IF EXISTS `weibo_trend`;
CREATE TABLE `weibo_trend`  (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '流水主键',
  `item_id` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL COMMENT '逻辑外键：MD5(title)',
  `rank_pos` int(11) NOT NULL COMMENT '当前排名',
  `heat` bigint(20) NOT NULL COMMENT '当前热度',
  `crawl_time` bigint(20) NOT NULL COMMENT '抓取时间戳 (毫秒)',
  `process_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '入库时间',
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `idx_item_time`(`item_id`, `crawl_time`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci COMMENT = '微博热搜趋势表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- View structure for view_weibo_summary_formatted
-- ----------------------------
DROP VIEW IF EXISTS `view_weibo_summary_formatted`;
CREATE ALGORITHM = UNDEFINED SQL SECURITY DEFINER VIEW `view_weibo_summary_formatted` AS SELECT 
  b.item_id,
  b.title AS '热搜标题',
  FROM_UNIXTIME(b.first_time / 1000) AS '首次上榜时间',
  IFNULL(a.type_name, '未知') AS '内容类型',
  CASE 
    WHEN a.sentiment_score > 0.3 THEN '正向'
    WHEN a.sentiment_score < -0.3 THEN '负向'
    ELSE '中性' 
  END AS '情感倾向',
  a.sentiment_score AS '原始情感分'
FROM weibo_base b
LEFT JOIN weibo_analysis a ON b.item_id = a.item_id ;

SET FOREIGN_KEY_CHECKS = 1;
