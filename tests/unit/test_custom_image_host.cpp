
/*
 * Copyright (C) Canonical, Ltd.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 */

#include "common.h"
#include "file_operations.h"
#include "mock_logger.h"
#include "mock_url_downloader.h"

#include <multipass/exceptions/download_exception.h>
#include <multipass/exceptions/image_not_found_exception.h>
#include <multipass/image_host/custom_image_host.h>
#include <multipass/logging/log.h>
#include <multipass/query.h>

#include <QUrl>

#include <boost/json.hpp>

namespace mp = multipass;
namespace mpt = multipass::test;

using namespace testing;

namespace
{
struct CustomImageHost : public Test
{
    CustomImageHost()
    {
    }

    mp::Query make_query(std::string release, std::string remote)
    {
        return {"", std::move(release), false, std::move(remote), mp::Query::Type::Alias};
    }

    QByteArray payload = mpt::load_test_file("custom_image_host/good_manifest.json");
    NiceMock<mpt::MockURLDownloader> mock_url_downloader;

    int num_images_for_arch(const QByteArray& manifest)
    {
        const auto arch = QSysInfo::currentCpuArchitecture().toStdString();
        auto images = boost::json::parse(std::string_view{manifest});

        int supported_count = 0;
        for (const auto& [_, distro] : images.as_object())
        {
            const auto items = distro.at("items").as_object();
            if (items.contains(arch))
                supported_count++;
        }

        return supported_count;
    }

    int num_total_distros(const QByteArray& manifest)
    {
        auto images = boost::json::parse(std::string_view{manifest});
        return static_cast<int>(images.as_object().size());
    }
};
} // namespace

TEST_F(CustomImageHost, iteratesOverAllEntries)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillRepeatedly(Return(payload));

    mp::CustomVMImageHost host{&mock_url_downloader};
    host.update_manifests(false);

    int supported_count = 0;
    int disabled_count = 0;
    auto action = [&](const std::string& remote, const mp::VMImageInfo& info) {
        if (info.disabled_reason.isEmpty())
            ++supported_count;
        else
            ++disabled_count;
    };
    host.for_each_entry_do(action);

    EXPECT_EQ(supported_count, num_images_for_arch(payload));
    EXPECT_EQ(supported_count + disabled_count, num_total_distros(payload));
}

TEST_F(CustomImageHost, allImagesForNoRemoteReturnsAppropriateMatches)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    auto images = host.all_images_for("", false);
    int supported_count = num_images_for_arch(payload);

    EXPECT_EQ(images.size(), supported_count);
}

TEST_F(CustomImageHost, allImagesForAllowUnsupportedIncludesDisabled)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    auto images = host.all_images_for("", true);

    EXPECT_EQ(static_cast<int>(images.size()), num_total_distros(payload));
    for (const auto& info : images)
    {
        const bool has_reason = !info.disabled_reason.isEmpty();
        EXPECT_EQ(has_reason, !info.supported);
    }
}

TEST_F(CustomImageHost, allInfoForNoRemoteReturnsOneAliasMatch)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    auto images_info = host.all_info_for(make_query("debian", ""));

    int supported_count = num_images_for_arch(payload);
    if (!supported_count)
    {
        SUCCEED() << "No images for current architecture";
        return;
    }

    EXPECT_EQ(images_info.size(), 1);
}

TEST_F(CustomImageHost, resolvesAliasesForAllDistros)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    const auto host_arch = QSysInfo::currentCpuArchitecture().toStdString();

    EXPECT_EQ(host.all_info_for(make_query("debian", "")).size(), 1u);
    EXPECT_EQ(host.all_info_for(make_query("fedora", "")).size(), 1u);
    EXPECT_EQ(host.all_info_for(make_query("alma", "")).size(), 1u);
    EXPECT_EQ(host.all_info_for(make_query("almalinux", "")).size(), 1u);
    EXPECT_EQ(host.all_info_for(make_query("rocky", "")).size(), 1u);
    EXPECT_EQ(host.all_info_for(make_query("rockylinux", "")).size(), 1u);

    // Arch only ships x86_64 upstream; on other architectures the manifest
    // entry is retained as a disabled record but hidden from info_for when
    // allow_unsupported is false, so the alias does not resolve by default.
    const size_t expected_arch_matches = (host_arch == "x86_64") ? 1u : 0u;
    EXPECT_EQ(host.all_info_for(make_query("arch", "")).size(), expected_arch_matches);
}

TEST_F(CustomImageHost, supportedRemotesReturnsExpectedValues)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    auto supported_remotes = host.supported_remotes();

    EXPECT_EQ(supported_remotes.size(), 1);

    EXPECT_TRUE(std::find(supported_remotes.begin(), supported_remotes.end(), "") !=
                supported_remotes.end());
}

TEST_F(CustomImageHost, invalidImageReturnsFalse)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    EXPECT_FALSE(host.info_for(make_query("foo", "")));
}

TEST_F(CustomImageHost, invalidRemoteThrowsError)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    EXPECT_THROW(host.info_for(make_query("core", "foo")), std::runtime_error);
}

TEST_F(CustomImageHost, handlesAndRecoversFromInitialNetworkFailure)
{
    EXPECT_CALL(mock_url_downloader, download(_, _))
        .WillOnce(Throw(mp::DownloadException{"", ""}))
        .WillRepeatedly(Return(payload));

    mp::CustomVMImageHost host{&mock_url_downloader};
    int supported_count = num_images_for_arch(payload);

    host.update_manifests(false);
    auto images_info = host.all_images_for("", false);
    EXPECT_EQ(images_info.size(), 0);

    host.update_manifests(false);
    images_info = host.all_images_for("", false);
    EXPECT_EQ(images_info.size(), supported_count);
}

TEST_F(CustomImageHost, handlesAndRecoversFromLaterNetworkFailure)
{
    EXPECT_CALL(mock_url_downloader, download(_, _))
        .WillOnce(Return(payload))
        .WillOnce(Throw(mp::DownloadException{"", ""}))
        .WillOnce(Return(payload));

    mp::CustomVMImageHost host{&mock_url_downloader};
    int supported_count = num_images_for_arch(payload);

    host.update_manifests(false);
    EXPECT_EQ(host.all_images_for("", false).size(), supported_count);

    host.update_manifests(false);
    EXPECT_EQ(host.all_images_for("", false).size(), 0);

    host.update_manifests(false);
    EXPECT_EQ(host.all_images_for("", false).size(), supported_count);
}

TEST_F(CustomImageHost, infoForFullHashReturnsEmptyImageInfo)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    EXPECT_THROW(host.info_for_full_hash("invalid-hash"), mp::ImageNotFoundException);
}

TEST_F(CustomImageHost, infoForFullHashFindsImageInfo)
{
    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(payload));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);
    int supported_count = num_images_for_arch(payload);

    if (!supported_count)
    {
        EXPECT_THROW(host.info_for_full_hash("debian-12-HASH"), mp::ImageNotFoundException);
        return;
    }

    const auto image = host.info_for_full_hash("debian-12-HASH");

    EXPECT_EQ(image.release, "bookworm");
}

TEST_F(CustomImageHost, badJsonLogsAndReturnsEmptyImages)
{
    const auto bad_json = mpt::load_test_file("custom_image_host/malformed_manifest.json");

    auto logger_scope = mpt::MockLogger::inject();
    logger_scope.mock_logger->screen_logs(multipass::logging::Level::warning);
    logger_scope.mock_logger->expect_log(
        multipass::logging::Level::warning,
        "Failed to parse manifest: file does not contain a valid JSON object");

    EXPECT_CALL(mock_url_downloader, download(_, _)).WillOnce(Return(bad_json));
    mp::CustomVMImageHost host{&mock_url_downloader};

    host.update_manifests(false);

    auto images = host.all_images_for("", false);

    EXPECT_EQ(images.size(), 0);
}
