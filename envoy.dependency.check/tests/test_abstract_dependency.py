
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from packaging import version

import pytest

import abstracts

from envoy.dependency.check import ADependency, exceptions


@abstracts.implementer(ADependency)
class DummyDependency:

    @property
    def release_class(self):
        return super().release_class


class DummyDependency2(DummyDependency):

    def __init__(self, id, metadata, github):
        self.id = id
        self.metadata = metadata
        self.github = github


def test_dependency_constructor(patches):

    with pytest.raises(TypeError):
        ADependency("ID", "METADATA", "GITHUB")

    dependency = DummyDependency("ID", "METADATA", "GITHUB")
    assert dependency.id == "ID"
    assert dependency.metadata == "METADATA"
    assert dependency.github == "GITHUB"


@pytest.mark.parametrize("id", range(0, 3))
@pytest.mark.parametrize("other_id", range(0, 3))
def test_dependency_dunder_gt(id, other_id):
    dependency1 = DummyDependency2(id, "METADATA", "GITHUB")
    dependency2 = DummyDependency2(other_id, "METADATA", "GITHUB")
    assert (dependency1 > dependency2) == (id > other_id)


@pytest.mark.parametrize("id", range(0, 3))
@pytest.mark.parametrize("other_id", range(0, 3))
def test_dependency_dunder_lt(id, other_id):
    dependency1 = DummyDependency2(id, "METADATA", "GITHUB")
    dependency2 = DummyDependency2(other_id, "METADATA", "GITHUB")
    assert (dependency1 < dependency2) == (id < other_id)


def test_dependency_dunder_str(patches):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.version",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_version, ):
        assert (
            str(dependency)
            == f"ID@{m_version.return_value}")


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [None] + list(range(0, 3)))
async def test_dependency_commits_since_current(patches, count):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.release",
         dict(new_callable=PropertyMock)),
        ("ADependency.repo",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_release, m_repo):
        m_repo.return_value.commits.return_value.total_count = AsyncMock(
            return_value=count)()
        m_release.return_value.timestamp_commit = AsyncMock(
            return_value="TIMESTAMP")()
        result = await dependency.commits_since_current
        assert (
            result
            == (count and count - 1 or count))

    assert (
        list(m_repo.return_value.commits.call_args)
        == [(), dict(since="TIMESTAMP")])
    assert (
        getattr(
            dependency,
            ADependency.commits_since_current.cache_name)[
                "commits_since_current"]
        == result)


@pytest.mark.parametrize(
    "urls",
    [[False, False, True],
     [False, False, False],
     [False, True, True]])
def test_dependency_github_url(patches, urls):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.urls",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    mock_urls = []
    expected_url = None
    for url in urls:
        mock_url = MagicMock()
        mock_url.startswith.return_value = url
        if url and not expected_url:
            expected_url = mock_url
        mock_urls.append(mock_url)

    with patched as (m_urls, ):
        m_urls.return_value = mock_urls
        assert dependency.github_url == expected_url

    for i, url in enumerate(urls):
        mock_url = mock_urls[i]
        assert (
            list(mock_url.startswith.call_args)
            == [('https://github.com/',), {}])
        if url:
            for other_url in mock_urls[i + 1:]:
                assert not other_url.startswith.called
            break
    assert "github_url" in dependency.__dict__


@pytest.mark.parametrize("archive", [True, False])
@pytest.mark.parametrize("endswith", [True, False])
def test_dependency_github_version(patches, archive, endswith):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.url_components",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")
    component = MagicMock()
    component.endswith.return_value = endswith

    def get_component(item):
        if archive and item == 5:
            return "archive"
        return component

    with patched as (m_components, ):
        m_components.return_value.__getitem__.side_effect = get_component
        result = dependency.github_version

    assert "github_version" in dependency.__dict__
    if not archive:
        assert result == component
        assert not component.__getitem__.called
        assert not component.endswith.called
        assert (
            list(list(c)
                 for c
                 in m_components.return_value.__getitem__.call_args_list)
            == [[(5, ), {}], [(7, ), {}]])
        return
    assert result == component.__getitem__.return_value
    assert (
        list(component.endswith.call_args)
        == [('.tar.gz', ), {}])
    assert (
        list(list(c)
             for c
             in m_components.return_value.__getitem__.call_args_list)
        == [[(5, ), {}], [(-1, ), {}], [(-1, ), {}]])
    if endswith:
        assert (
            list(component.__getitem__.call_args)
            == [(slice(None, -len('.tar.gz')), ), {}])
        return
    assert (
        list(component.__getitem__.call_args)
        == [(slice(None, -len('.zip')), ), {}])


@pytest.mark.parametrize("tagged", [True, False])
def test_dependency_github_version_name(patches, tagged):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.github_version",
         dict(new_callable=PropertyMock)),
        ("ADependency.release",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_version, m_release):
        m_release.return_value.tagged = tagged
        assert (
            dependency.github_version_name
            == (m_version.return_value.__getitem__.return_value
                if not tagged
                else m_version.return_value))

    assert "github_version_name" not in dependency.__dict__
    if tagged:
        assert not m_version.return_value.__getitem__.called
        return
    assert (
        list(m_version.return_value.__getitem__.call_args)
        == [(slice(0, 7), ), {}])


@pytest.mark.asyncio
@pytest.mark.parametrize("commits", range(0, 5))
async def test_dependency_has_recent_commits(patches, commits):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.recent_commits",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_recent, ):
        m_recent.return_value = AsyncMock(return_value=commits)()
        assert await dependency.has_recent_commits == (commits > 1)

    assert not getattr(
        dependency,
        ADependency.has_recent_commits.cache_name,
        None)


@pytest.mark.asyncio
@pytest.mark.parametrize("newest", [None, "BINGO", "BLOOP"])
async def test_dependency_newer_release(patches, newest):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        "version",
        ("ADependency.release",
         dict(new_callable=PropertyMock)),
        ("ADependency.release_class",
         dict(new_callable=PropertyMock)),
        ("ADependency.repo",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    if newest:
        newer_release = MagicMock()
        newer_release.tag_name = newest
    else:
        newer_release = None

    with patched as (m_version, m_release, m_class, m_repo):
        m_version.parse.side_effect = lambda x: x
        m_release.return_value.version = "BLOOP"
        timestamp = AsyncMock()
        m_release.return_value.timestamp = timestamp()
        m_repo.return_value.highest_release = AsyncMock(
            return_value=newer_release)
        result = await dependency.newer_release
        assert (
            result
            == (m_class.return_value.return_value
                if newest and newest != "BLOOP"
                else None))

    if newest and newest != "BLOOP":
        assert (
            list(m_class.return_value.call_args)
            == [(m_repo.return_value, newest),
                dict(release=newer_release)])
    else:
        assert not m_class.called
    assert (
        list(m_repo.return_value.highest_release.call_args)
        == [(), dict(since=timestamp.return_value)])
    assert (
        getattr(
            dependency,
            ADependency.newer_release.cache_name)[
                "newer_release"]
        == result)


def test_dependency_organization(patches):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.url_components",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_components, ):
        assert (
            dependency.organization
            == m_components.return_value.__getitem__.return_value)

    assert (
        list(m_components.return_value.__getitem__.call_args)
        == [(3, ), {}])
    assert "organization" not in dependency.__dict__


def test_dependency_project(patches):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.url_components",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_components, ):
        assert (
            dependency.project
            == m_components.return_value.__getitem__.return_value)

    assert (
        list(m_components.return_value.__getitem__.call_args)
        == [(4, ), {}])
    assert "project" not in dependency.__dict__


@pytest.mark.asyncio
@pytest.mark.parametrize("tagged", [True, False])
async def test_dependency_recent_commits(patches, tagged):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.commits_since_current",
         dict(new_callable=PropertyMock)),
        ("ADependency.release",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_commits, m_release):
        m_release.return_value.tagged = tagged
        commits = AsyncMock()
        m_commits.side_effect = commits
        result = await dependency.recent_commits
        assert (
            result
            == (commits.return_value
                if not tagged
                else 0))

    assert (
        getattr(
            dependency,
            ADependency.recent_commits.cache_name)[
                "recent_commits"]
        == result)


def test_dependency_release(patches):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.github_version",
         dict(new_callable=PropertyMock)),
        ("ADependency.release_class",
         dict(new_callable=PropertyMock)),
        ("ADependency.repo",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_version, m_class, m_repo):
        assert dependency.release == m_class.return_value.return_value

    assert (
        list(m_class.return_value.call_args)
        == [(m_repo.return_value, m_version.return_value), {}])
    assert "release" in dependency.__dict__


def test_dependency_release_date():
    metadata = MagicMock()
    dependency = DummyDependency2("ID", metadata, "GITHUB")
    assert dependency.release_date == metadata.__getitem__.return_value
    assert "release_date" not in dependency.__dict__


@pytest.mark.asyncio
@pytest.mark.parametrize("date1", range(0, 5))
@pytest.mark.parametrize("date2", range(0, 5))
async def test_dependency_release_date_mismatch(patches, date1, date2):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.release",
         dict(new_callable=PropertyMock)),
        ("ADependency.release_date",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_release, m_date):
        m_date.return_value = date1
        m_release.return_value.date = AsyncMock(return_value=date2)()
        assert await dependency.release_date_mismatch == (date1 != date2)

    assert not getattr(
        dependency,
        ADependency.release_date_mismatch.cache_name,
        None)


@pytest.mark.parametrize("raises", [None, version.InvalidVersion, Exception])
def test_dependency_release_version(patches, raises):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        "version.Version",
        ("ADependency.version", dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_version, m_dep_version):
        if raises:
            m_version.side_effect = raises
        if raises == Exception:
            with pytest.raises(Exception):
                dependency.release_version
        else:
            assert (
                dependency.release_version
                == (m_version.return_value if not raises else None))

    assert (
        list(m_version.call_args)
        == [(m_dep_version.return_value, ), {}])
    if raises != Exception:
        assert "release_version" in dependency.__dict__


def test_dependency_repo(patches):
    github = MagicMock()
    dependency = DummyDependency2("ID", "METADATA", github)
    patched = patches(
        ("ADependency.organization",
         dict(new_callable=PropertyMock)),
        ("ADependency.project",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")

    with patched as (m_org, m_project):
        assert (
            dependency.repo
            == github.__getitem__.return_value)

    assert (
        list(github.__getitem__.call_args)
        == [(f"{m_org.return_value}/{m_project.return_value}", ), {}])
    assert "repo" in dependency.__dict__


@pytest.mark.parametrize("github_url", [True, False])
def __test_dependency_url_components(patches, github_url):
    dependency = DummyDependency2("ID", "METADATA", "GITHUB")
    patched = patches(
        ("ADependency.github_url",
         dict(new_callable=PropertyMock)),
        ("ADependency.urls",
         dict(new_callable=PropertyMock)),
        prefix="envoy.dependency.check.abstract.dependency")
    urls = [f"URL{i}" for i in range(0, 5)]

    with patched as (m_url, m_urls):
        if not github_url:
            m_url.return_value = None
        m_urls.return_value = urls

        if not github_url:
            with pytest.raises(exceptions.NotDependency) as e:
                dependency.url_components
            urls = "\n".join(urls)
            assert (
                e.value.args[0]
                == f'ID is not a GitHub repository\n{urls}')
        else:
            assert (
                dependency.url_components
                == m_url.return_value.split.return_value)

    if github_url:
        assert (
            list(m_url.return_value.split.call_args)
            == [("/", ), {}])
        assert "url_components" in dependency.__dict__


def test_dependency_urls():
    metadata = MagicMock()
    dependency = DummyDependency2("ID", metadata, "GITHUB")
    assert dependency.urls == metadata.__getitem__.return_value
    assert "release_date" not in dependency.__dict__


def test_dependency_version():
    metadata = MagicMock()
    dependency = DummyDependency2("ID", metadata, "GITHUB")
    assert dependency.version == metadata.__getitem__.return_value
    assert "release_date" not in dependency.__dict__
