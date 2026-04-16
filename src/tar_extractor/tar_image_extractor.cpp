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

#include <multipass/tar_image_extractor.h>

#include <fmt/format.h>

#include <array>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>

namespace mp = multipass;

namespace
{

std::string run_command(const std::string& cmd)
{
    std::array<char, 4096> buffer{};
    std::string result;
    auto* pipe = popen(cmd.c_str(), "r");
    if (!pipe)
        throw std::runtime_error("Failed to run command: " + cmd);
    while (std::fgets(buffer.data(), buffer.size(), pipe))
        result += buffer.data();
    auto status = pclose(pipe);
    if (status != 0)
        throw std::runtime_error(fmt::format("Command failed (exit {}): {}", status, cmd));
    return result;
}

std::string shell_quote(const std::string& s)
{
    std::string result = "'";
    for (char c : s)
    {
        if (c == '\'')
            result += "'\\''";
        else
            result += c;
    }
    result += "'";
    return result;
}

} // namespace

std::filesystem::path mp::extract_first_file_from_tar(const std::filesystem::path& tar_path,
                                                      bool delete_tar)
{
    if (!std::filesystem::exists(tar_path))
        throw std::runtime_error(fmt::format("Tar archive does not exist: {}", tar_path.string()));

    const auto parent = tar_path.parent_path();
    const auto quoted_tar = shell_quote(tar_path.string());
    const auto quoted_dir = shell_quote(parent.string());

    // List the first regular file in the archive
    auto listing = run_command(fmt::format("tar tf {} | head -1", quoted_tar));
    while (!listing.empty() && (listing.back() == '\n' || listing.back() == '\r'))
        listing.pop_back();
    if (listing.empty())
        throw std::runtime_error(fmt::format("Tar archive is empty: {}", tar_path.string()));

    // Extract into the parent directory
    run_command(fmt::format("tar xf {} -C {}", quoted_tar, quoted_dir));

    auto extracted = parent / std::filesystem::path(listing).filename();
    if (!std::filesystem::exists(extracted))
        throw std::runtime_error(
            fmt::format("Expected extracted file not found: {}", extracted.string()));

    if (delete_tar)
    {
        std::error_code ec;
        std::filesystem::remove(tar_path, ec);
    }

    return extracted;
}
